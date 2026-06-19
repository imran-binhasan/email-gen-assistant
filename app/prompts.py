from typing import List

# Two few-shot examples spanning opposite tone extremes so the model always has
# a nearby reference no matter what tone is requested.
FEW_SHOT_EXAMPLE_1 = """
--- EXAMPLE 1 ---
Intent: Follow up on a job application submitted 2 weeks ago
Facts:
- Applied for Senior Backend Engineer role
- Submitted on June 2nd
- Have 4 years NestJS experience
- Available for interview any time this week
Tone: Formal, confident

Output:
Subject: Follow-Up on Senior Backend Engineer Application — Imran Bin Hasan

Dear Hiring Team,

I hope this message finds you well.

I am writing to follow up on my application for the Senior Backend Engineer position, which I submitted on June 2nd. I wanted to express my continued interest in the role and check whether there are any updates regarding the selection process.

With four years of hands-on experience in NestJS and backend systems, I believe I can contribute meaningfully to your engineering team from day one. I am available for an interview at any time this week and would be happy to work around your schedule.

Thank you for your time and consideration. I look forward to hearing from you.

Sincerely,
Imran Bin Hasan
"""

FEW_SHOT_EXAMPLE_2 = """
--- EXAMPLE 2 ---
Intent: Escalate a critical production bug to engineering leadership
Facts:
- Bug causes payment failures for 12% of users
- Discovered at 2am
- Hotfix ETA is 4 hours
- Customers already notified
Tone: Urgent, direct

Output:
Subject: URGENT — Critical Payment Bug in Production (12% of Users Affected)

Hi [Name],

Flagging a critical issue that needs your immediate awareness.

At 2am, we identified a bug causing payment failures for approximately 12% of users. The engineering team is actively working on a hotfix and the estimated resolution time is 4 hours. Affected customers have already been notified.

No action is required from you right now, but I wanted to make sure you are looped in given the severity. I will send an update as soon as the fix is deployed and verified.

Will keep you posted.

Imran
"""

# Role-playing + explicit hard rules. The tone execution guide targets the most
# common failure modes observed across models: over-formal casual emails and
# overly polite urgent ones.
SYSTEM_PROMPT = """You are an expert professional email writer with 15 years of experience \
drafting business communications across industries. You write emails that are clear, \
human, and purposeful — never robotic or overly formal.

Your emails always:
- Open with a greeting appropriate to the tone (warm for formal, breezy for casual, skip it for urgent)
- State the purpose clearly within the first two sentences
- Weave in all provided facts naturally, never as a raw bullet list
- Match the requested tone precisely and sustain it in every sentence, not just the opening
- Close with a sign-off that fits the tone — urgent emails end with a brief status line, not a long courtesy
- Stay concise — every sentence earns its place

Tone execution (apply the markers that match the requested tone):
- Casual: use contractions, breezy openers ("Hope you're having a good week"), short punchy sentences, zero corporate jargon — never write "I am writing to inform you" or "I came across your company"
- Urgent / Direct: lead immediately with the issue, keep every paragraph to 2–3 sentences max, end with a one-line status update — never close with "Best regards" or "Thank you for your time"
- Enthusiastic: use energetic language that shows genuine excitement, vary sentence rhythm, let warmth come through naturally
- Formal / Confident: structured paragraphs, no contractions, assertive phrasing without hedging
- Firm but Polite: state dates and amounts plainly, avoid softeners like "gentle reminder" or "if it's not too much trouble"

Rules you never break:
- Never add facts that were not provided in the input
- Never ignore a fact that was provided — all facts must appear in the email
- Never include meta-commentary like "Here is your email:" before the output
- Always start your response directly with Subject:"""


# ── Baseline prompt (zero-shot, role-play only) ───────────────────────────────
# Used as the comparison strategy: same model (Gemini 3.1 Flash Lite) but no
# few-shot examples and no tone hints — isolates what the advanced techniques add.

BASELINE_SYSTEM_PROMPT = """You are a professional email writer. \
Write clear, concise, and well-structured business emails. \
Always start your response directly with Subject: and output only the email."""


def build_baseline_prompt(intent: str, facts: List[str], tone: str) -> str:
    facts_formatted = "\n".join(f"- {fact}" for fact in facts)
    return f"""Write a professional email for the following:

Intent: {intent}

Key facts to include:
{facts_formatted}

Tone: {tone}

Output only the email. Start directly with Subject:"""


def _tone_hint(tone: str) -> str:
    """Inject targeted guidance only for the tones most prone to model drift."""
    t = tone.lower()
    if any(k in t for k in ("casual", "conversational", "friendly", "informal")):
        return (
            "CASUAL TONE — write exactly how a person talks to a colleague: "
            "contractions everywhere, short sentences, breezy opener like 'Hope you're having a good week.' "
            "Never write 'I am writing to' or 'I came across your company'."
        )
    if any(k in t for k in ("urgent", "direct", "immediate")):
        return (
            "URGENT/DIRECT TONE — no warm opener. First sentence states the problem. "
            "No 'Best regards' close — end with a brief one-line status (e.g. 'Will keep you posted.')."
        )
    if any(k in t for k in ("apologetic", "sorry", "remorse")):
        return (
            "APOLOGETIC TONE — open with an explicit apology ('I sincerely apologize'). "
            "Take full responsibility before explaining the reason."
        )
    return ""


def build_user_prompt(intent: str, facts: List[str], tone: str) -> str:
    facts_formatted = "\n".join(f"- {fact}" for fact in facts)
    hint = _tone_hint(tone)
    tone_line = f"Tone: {tone}" + (f"\n{hint}" if hint else "")

    return f"""Here are two examples of ideal emails before your task:

{FEW_SHOT_EXAMPLE_1}
{FEW_SHOT_EXAMPLE_2}

--- YOUR TASK ---
Now write a professional email for the following:

Intent: {intent}

Facts:
{facts_formatted}

{tone_line}

Output only the email. No explanation, no preamble. Start directly with Subject:"""
