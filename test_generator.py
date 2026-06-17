from app.generator import generate_mail

intent = "Follow up on a job application submitted 2 weeks ago"
facts  = [
    "Applied for Senior Backend Engineer role",
    "Submitted on June 2nd",
    "Have 4 years NestJS experience",
    "Available for interview any time this week"
]
tone = "Formal, confident"

print("=== GEMINI ===")
print(generate_mail(intent, facts, tone, model="gemini"))

print("\n=== GROQ ===")
print(generate_mail(intent, facts, tone, model="groq"))