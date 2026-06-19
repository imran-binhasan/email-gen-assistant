import os
import json
from google import genai
from groq import Groq
from rouge_score import rouge_scorer
from dotenv import load_dotenv

load_dotenv()

# ── Judge clients ──────────────────────────────────────────────────────────────
# Same clients as generator but used exclusively for judging.
# Keeping them here makes the evaluator self-contained.

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client   = Groq(api_key=os.getenv("GROQ_API_KEY"))

GEMINI_JUDGE_MODEL = "gemini-2.5-flash"
GROQ_JUDGE_MODEL   = "llama-3.3-70b-versatile"


# ── Judge caller ───────────────────────────────────────────────────────────────
# Single function that routes to the correct judge model.
# Returns raw text response from the judge.

def _call_judge(prompt: str, judge_model: str) -> str:
    """
    Call the judge LLM with a scoring prompt.
    Returns the raw text response.

    Args:
        prompt:      The full scoring prompt including all context
        judge_model: "gemini" or "groq"
    """
    if judge_model == "gemini":
        response = gemini_client.models.generate_content(
            model=GEMINI_JUDGE_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.0,  # zero temp for consistent, deterministic scoring
            )
        )
        return response.text.strip()

    elif judge_model == "groq":
        response = groq_client.chat.completions.create(
            model=GROQ_JUDGE_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,  # zero temp for consistent, deterministic scoring
        )
        return response.choices[0].message.content.strip()

    else:
        raise ValueError(f"Unsupported judge model: {judge_model}")


# ── Score parser ───────────────────────────────────────────────────────────────
# LLM responses are text — we need to extract the numeric score reliably.
# This looks for the first float or int in the response.

def _parse_score(text: str) -> float:
    """
    Extract the first valid float score (0.0 to 1.0) from judge response.
    Falls back to 0.0 if nothing valid is found.
    """
    import re
    matches = re.findall(r'\b(0?\.\d+|1\.0|0\.0|1|0)\b', text)
    for match in matches:
        try:
            score = float(match)
            if 0.0 <= score <= 1.0:
                return score
        except ValueError:
            continue
    return 0.0  # safe fallback


# ── Metric 1: Fact Recall Score ────────────────────────────────────────────────
# Measures whether every input fact appears in the generated email.
# Uses LLM-as-a-Judge for semantic matching (handles paraphrasing).
#
# Logic:
#   - Judge checks each fact individually against the generated email
#   - Returns score: (facts present) / (total facts)
#   - Score 1.0 = all facts included, 0.0 = no facts included

def fact_recall_score(
    facts: list[str],
    generated_email: str,
    judge_model: str
) -> dict:
    """
    Metric 1: Fact Recall Score

    Checks whether all input facts are present in the generated email.
    Uses LLM-as-a-Judge to handle semantic equivalence and paraphrasing.

    Returns:
        dict with 'score' (float) and 'justification' (str)
    """
    facts_formatted = "\n".join(f"{i+1}. {fact}" for i, fact in enumerate(facts))

    prompt = f"""You are an objective email quality evaluator.

Your task: Check whether each of the following facts appears in the generated email.
A fact is considered present even if it is paraphrased, as long as the meaning is preserved.

Facts to check:
{facts_formatted}

Generated email:
{generated_email}

Instructions:
- For each fact, decide: present (1) or missing (0)
- Calculate the score as: number of present facts / total facts
- Round to 2 decimal places
- Respond in this exact JSON format with no extra text:

{{
  "fact_checks": [
    {{"fact": "fact text here", "present": true, "reason": "brief reason"}},
    ...
  ],
  "score": 0.00,
  "justification": "one sentence summary"
}}"""

    raw = _call_judge(prompt, judge_model)

    try:
        # Strip markdown code fences if judge wraps in ```json
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return {
            "score": float(result.get("score", 0.0)),
            "justification": result.get("justification", "No justification provided")
        }
    except (json.JSONDecodeError, KeyError):
        # Fallback: try to parse a score from raw text
        return {
            "score": _parse_score(raw),
            "justification": raw[:200]
        }


# ── Metric 2: Tone Alignment Score ────────────────────────────────────────────
# Measures whether the generated email matches the requested tone.
# Uses LLM-as-a-Judge because tone is subjective and contextual.
#
# Logic:
#   - Judge reads the requested tone and the full email
#   - Rates alignment from 0.0 (completely wrong tone) to 1.0 (perfect match)
#   - Must provide justification to prevent arbitrary scoring

def tone_alignment_score(
    tone: str,
    generated_email: str,
    judge_model: str
) -> dict:
    """
    Metric 2: Tone Alignment Score

    Evaluates how well the generated email matches the requested tone.
    Uses LLM-as-a-Judge with mandatory justification.

    Returns:
        dict with 'score' (float) and 'justification' (str)
    """
    prompt = f"""You are an objective email quality evaluator.

Your task: Rate how well the generated email matches the requested tone.

Requested tone: {tone}

Generated email:
{generated_email}

Scoring guide:
- 1.0 = Tone is perfectly maintained throughout the entire email
- 0.75 = Tone is mostly correct with minor inconsistencies
- 0.5 = Tone is partially correct but noticeably inconsistent
- 0.25 = Tone is mostly incorrect
- 0.0 = Tone is completely wrong or opposite to what was requested

Respond in this exact JSON format with no extra text:

{{
  "score": 0.00,
  "justification": "one sentence explaining your rating"
}}"""

    raw = _call_judge(prompt, judge_model)

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        return {
            "score": float(result.get("score", 0.0)),
            "justification": result.get("justification", "No justification provided")
        }
    except (json.JSONDecodeError, KeyError):
        return {
            "score": _parse_score(raw),
            "justification": raw[:200]
        }


# ── Metric 3: Fluency Score (Hybrid) ──────────────────────────────────────────
# Combines LLM-as-a-Judge (professionalism) with ROUGE-L (structural similarity).
# This is the methodologically richest metric — shows automated + LLM combination.
#
# Logic:
#   - LLM judge rates professionalism/fluency: 0.0 to 1.0
#   - ROUGE-L computes longest common subsequence overlap with reference: 0.0 to 1.0
#   - Final score = (llm_score + rouge_score) / 2

def fluency_score(
    generated_email: str,
    reference_email: str,
    judge_model: str
) -> dict:
    """
    Metric 3: Fluency Score (Hybrid)

    Combines:
    - LLM-as-a-Judge for professionalism and writing quality
    - ROUGE-L for structural similarity to the human reference email

    Final score = average of both components.

    Returns:
        dict with 'score', 'llm_score', 'rouge_l_score', 'justification'
    """

    # ── Component A: LLM professionalism judge ─────────────────────────────────
    prompt = f"""You are an objective email quality evaluator.

Your task: Rate the overall fluency, grammar, and professionalism of this email.

Generated email:
{generated_email}

Scoring guide:
- 1.0 = Exceptionally well-written, professional, ready to send as-is
- 0.75 = Good quality with minor issues
- 0.5 = Acceptable but with noticeable grammar or professionalism issues
- 0.25 = Poor quality, significant issues
- 0.0 = Unacceptable, unprofessional, or incoherent

Respond in this exact JSON format with no extra text:

{{
  "score": 0.00,
  "justification": "one sentence explaining your rating"
}}"""

    raw = _call_judge(prompt, judge_model)

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean)
        llm_score     = float(result.get("score", 0.0))
        justification = result.get("justification", "No justification provided")
    except (json.JSONDecodeError, KeyError):
        llm_score     = _parse_score(raw)
        justification = raw[:200]

    # ── Component B: ROUGE-L automated score ───────────────────────────────────
    scorer      = rouge_scorer.RougeScorer(["rougeL"], use_stemmer=True)
    rouge_scores = scorer.score(reference_email, generated_email)
    rouge_l      = round(rouge_scores["rougeL"].fmeasure, 4)

    # ── Final hybrid score ─────────────────────────────────────────────────────
    final_score = round((llm_score + rouge_l) / 2, 4)

    return {
        "score":        final_score,
        "llm_score":    llm_score,
        "rouge_l_score": rouge_l,
        "justification": justification
    }


# ── Master evaluation function ─────────────────────────────────────────────────
# Runs all 3 metrics for a single scenario.
# Called by run_eval.py for each of the 10 scenarios × 2 models.

def evaluate(
    facts: list[str],
    tone: str,
    generated_email: str,
    reference_email: str,
    generator_model: str  # "gemini" or "groq" — determines which model judges
) -> dict:
    """
    Run all 3 metrics for one generated email.

    Judge is always the opposite of the generator to avoid self-grading bias:
    - gemini generated → groq judges
    - groq generated   → gemini judges

    Returns:
        dict with all 3 metric results
    """
    judge = "groq" if generator_model == "gemini" else "gemini"

    m1 = fact_recall_score(facts, generated_email, judge)
    m2 = tone_alignment_score(tone, generated_email, judge)
    m3 = fluency_score(generated_email, reference_email, judge)

    return {
        "fact_recall":     m1,
        "tone_alignment":  m2,
        "fluency":         m3,
        "judge_model":     judge,
    }