from typing import List

# ── Few-shot examples ──────────────────────────────────────────────────────────
# Deliberately chosen to cover opposite tone extremes:
#   Example 1 → formal/confident
#   Example 2 → urgent/direct
# This ensures the model has a nearby reference point for any tone requested.

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

# ── System prompt (Role-Playing layer) ────────────────────────────────────────
# This establishes the model's persona and hard behavioral rules.
# The explicit "never add / never ignore" instruction directly addresses
# the most common failure mode of email generators.

SYSTEM_PROMPT = """You are an expert professional email writer with 15 years of experience \
drafting business communications across industries. You write emails that are clear, \
human, and purposeful — never robotic or overly formal.

Your emails always:
- Open with a warm but professional greeting appropriate to the tone
- State the purpose clearly within the first two sentences
- Weave in all provided facts naturally, never as a raw bullet list
- Match the requested tone precisely and consistently throughout
- Close with a polite, appropriate sign-off that fits the tone
- Stay concise — every sentence earns its place

Rules you never break:
- Never add facts that were not provided in the input
- Never ignore a fact that was provided — all facts must appear in the email
- Never include meta-commentary like "Here is your email:" before the output
- Always start your response directly with Subject:"""


# ── User prompt builder ────────────────────────────────────────────────────────
# Combines few-shot examples + the actual task into one user message.
# facts is a list of strings, formatted as bullet points automatically.

def build_user_prompt(intent: str, facts: List[str], tone: str) -> str:
    facts_formatted = "\n".join(f"- {fact}" for fact in facts)

    return f"""Here are two examples of ideal emails before your task:

{FEW_SHOT_EXAMPLE_1}
{FEW_SHOT_EXAMPLE_2}

--- YOUR TASK ---
Now write a professional email for the following:

Intent: {intent}

Facts:
{facts_formatted}

Tone: {tone}

Output only the email. No explanation, no preamble. Start directly with Subject:"""