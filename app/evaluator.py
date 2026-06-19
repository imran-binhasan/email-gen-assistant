import os
import re
import json
import time
from google import genai
from groq import Groq
from rouge_score import rouge_scorer
from dotenv import load_dotenv
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client   = Groq(api_key=os.getenv("GROQ_API_KEY"))

GEMINI_JUDGE_MODEL = "gemini-3.1-flash-lite"   # 500 RPD free tier
GROQ_JUDGE_MODEL   = "llama-3.3-70b-versatile"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=10, max=90))
def _call_judge(prompt: str, judge_model: str) -> str:
    if judge_model == "gemini":
        response = gemini_client.models.generate_content(
            model=GEMINI_JUDGE_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(temperature=0.0),
        )
        return response.text.strip()
    elif judge_model == "groq":
        response = groq_client.chat.completions.create(
            model=GROQ_JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return response.choices[0].message.content.strip()
    else:
        raise ValueError(f"Unsupported judge model: {judge_model}")


def _parse_score(text: str) -> float:
    """Fallback: extract first valid 0–1 float from free-text judge response."""
    for match in re.findall(r'\b(0?\.\d+|1\.0|0\.0|1|0)\b', text):
        try:
            score = float(match)
            if 0.0 <= score <= 1.0:
                return score
        except ValueError:
            continue
    return 0.0


def fact_recall_score(facts: list[str], generated_email: str, judge_model: str) -> dict:
    """Metric 1 — fraction of input facts semantically present in the email."""
    facts_formatted = "\n".join(f"{i+1}. {fact}" for i, fact in enumerate(facts))

    prompt = f"""You are an objective email quality evaluator.

Task: Check whether each fact below appears in the generated email.
A fact counts as present even if paraphrased, as long as the meaning is preserved.

Facts to check:
{facts_formatted}

Generated email:
{generated_email}

Instructions:
- For each fact decide: present (true) or missing (false)
- Score = present_count / total_facts, rounded to 2 decimal places
- Reply ONLY with this JSON, no extra text:

{{
  "fact_checks": [
    {{"fact": "...", "present": true, "reason": "..."}}
  ],
  "score": 0.00,
  "justification": "one sentence summary"
}}"""

    raw = _call_judge(prompt, judge_model)
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return {
            "score": float(result.get("score", 0.0)),
            "justification": result.get("justification", ""),
        }
    except (json.JSONDecodeError, KeyError):
        return {"score": _parse_score(raw), "justification": raw[:200]}


def tone_alignment_score(tone: str, generated_email: str, judge_model: str) -> dict:
    """Metric 2 — how well the email sustains the requested tone."""
    prompt = f"""You are an objective email quality evaluator.

Task: Rate how well the generated email matches the requested tone.

Requested tone: {tone}

Generated email:
{generated_email}

Scoring:
1.0 = tone perfectly maintained throughout
0.75 = mostly correct, minor slip
0.5 = partially correct, noticeable inconsistency
0.25 = mostly wrong tone
0.0 = completely wrong

Reply ONLY with this JSON, no extra text:

{{
  "score": 0.00,
  "justification": "one sentence"
}}"""

    raw = _call_judge(prompt, judge_model)
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return {
            "score": float(result.get("score", 0.0)),
            "justification": result.get("justification", ""),
        }
    except (json.JSONDecodeError, KeyError):
        return {"score": _parse_score(raw), "justification": raw[:200]}


def fluency_score(generated_email: str, reference_email: str, judge_model: str) -> dict:
    """Metric 3 — hybrid: LLM professionalism score averaged with ROUGE-L vs reference."""
    prompt = f"""You are an objective email quality evaluator.

Task: Rate the fluency, grammar, and professional quality of this email.

Generated email:
{generated_email}

Scoring:
1.0 = excellent, ready to send
0.75 = good, minor issues
0.5 = acceptable but noticeable problems
0.25 = poor quality
0.0 = unprofessional or incoherent

Reply ONLY with this JSON, no extra text:

{{
  "score": 0.00,
  "justification": "one sentence"
}}"""

    raw = _call_judge(prompt, judge_model)
    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        llm_score     = float(result.get("score", 0.0))
        justification = result.get("justification", "")
    except (json.JSONDecodeError, KeyError):
        llm_score     = _parse_score(raw)
        justification = raw[:200]

    scorer      = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rouge_l     = round(scorer.score(reference_email, generated_email)["rougeL"].fmeasure, 4)
    final_score = round((llm_score + rouge_l) / 2, 4)

    return {
        "score":         final_score,
        "llm_score":     llm_score,
        "rouge_l_score": rouge_l,
        "justification": justification,
    }


def evaluate(
    facts: list[str],
    tone: str,
    generated_email: str,
    reference_email: str,
    generator_model: str,
) -> dict:
    # Gemini is the single consistent judge for all models.
    # Original design used cross-judging (gemini↔groq) but Groq's free-tier
    # TPM limits made it unreliable for the 30 high-token judge calls per run.
    # A single judge also improves score comparability across models.
    judge = "gemini"

    m1 = fact_recall_score(facts, generated_email, judge)
    time.sleep(5)  # stay under gemini-3.1-flash-lite 15 RPM ceiling
    m2 = tone_alignment_score(tone, generated_email, judge)
    time.sleep(5)
    m3 = fluency_score(generated_email, reference_email, judge)

    return {
        "fact_recall":    m1,
        "tone_alignment": m2,
        "fluency":        m3,
        "judge_model":    judge,
    }
