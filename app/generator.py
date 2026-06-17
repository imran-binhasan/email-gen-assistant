import os
from groq import Groq
from google import genai
from dotenv import load_dotenv
from app.prompts import SYSTEM_PROMPT, build_user_prompt
from typing import List

load_dotenv()

# Client initialization
gemini_client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

groq_client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

GEMINI_MODEL = "gemini-3-flash-preview"
GROQ_MODEL   = "llama-3.3-70b-versatile"

def generate_with_gemini(intent: str, facts: List[str], tone: str) -> str:
    """
    Generate an email using Gemini 2.0 Flash.

    google-genai 2.x SDK uses client.models.generate_content()
    with a config object for system instruction.
    """
    user_prompt = build_user_prompt(intent, facts, tone)

    response = gemini_client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.7,
        )
    )
    return response.text.strip()




def generate_with_grok(intent: str, facts: List[str], tone: str) -> str:
    """
    Generate an email using Groq (Llama 3.3 70B).

    Groq follows the standard OpenAI-compatible messages format,
    so system prompt goes in the system role and user prompt
    in the user role — clean separation maintained.
    """

    user_prompt = build_user_prompt(intent, facts, tone)
    response = groq_client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[
            {"role":"system", "content":SYSTEM_PROMPT},
            {"role":"user", "content":user_prompt},
        ],
        temperature=0.7,
    )

    return response.choices[0].message.content.strip()



def generate_mail(
        intent: str,
        facts: List[str],
        tone: str,
        model: str = "gemini"
) -> str:
    """" 
    Args:
        intent: The core purpose of the email
        facts:  List of key facts to include
        tone:   Desired tone/style
        model:  "gemini" or "groq"
    """
    if model == "gemini":
        return generate_with_gemini(intent,facts,tone)
    elif model == "groq":
        return generate_with_grok(intent, facts, tone)
    else:
        raise ValueError(f"Unsupported model: '{model}'. Choose 'gemini' or 'groq'. ")