import os
from groq import Groq
from google import genai
from dotenv import load_dotenv
from app.prompts import SYSTEM_PROMPT, build_user_prompt, BASELINE_SYSTEM_PROMPT, build_baseline_prompt
from typing import List
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

gemini_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
groq_client   = Groq(api_key=os.getenv("GROQ_API_KEY"))

GEMINI_MODEL = "gemini-3.1-flash-lite"   # 500 RPD free tier
GROQ_MODEL   = "llama-3.3-70b-versatile"


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=10, max=90))
def generate_with_gemini(intent: str, facts: List[str], tone: str) -> str:
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_user_prompt(intent, facts, tone),
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
        ),
    )
    return response.text.strip()


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=15, max=60))
def generate_with_grok(intent: str, facts: List[str], tone: str) -> str:
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": build_user_prompt(intent, facts, tone)},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


@retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=2, min=10, max=90))
def generate_with_gemini_baseline(intent: str, facts: List[str], tone: str) -> str:
    """Zero-shot baseline: same model (Gemini 3.1 Flash Lite) but no few-shot examples or tone hints."""
    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=build_baseline_prompt(intent, facts, tone),
        config=genai.types.GenerateContentConfig(
            system_instruction=BASELINE_SYSTEM_PROMPT,
            temperature=0.7,
        ),
    )
    return response.text.strip()


def generate_mail(intent: str, facts: List[str], tone: str, model: str = "gemini") -> str:
    if model == "gemini":
        return generate_with_gemini(intent, facts, tone)
    elif model == "gemini_baseline":
        return generate_with_gemini_baseline(intent, facts, tone)
    elif model == "groq":
        return generate_with_grok(intent, facts, tone)
    else:
        raise ValueError(f"Unsupported model: '{model}'. Choose 'gemini', 'gemini_baseline', or 'groq'.")
