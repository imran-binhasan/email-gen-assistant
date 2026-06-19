import json
import csv
import time
import os
import sys
from app.generator import generate_mail
from app.evaluator import evaluate

# Force line-buffered stdout so progress is visible when piped to a file
sys.stdout.reconfigure(line_buffering=True)

# ── Load data ──────────────────────────────────────────────────────────────────

with open("data/scenarios.json", "r") as f:
    scenarios = json.load(f)

with open("data/references.json", "r") as f:
    references = json.load(f)

# Build a quick lookup dict: scenario id → reference email
reference_map = {r["id"]: r["reference"] for r in references}

# ── Config ─────────────────────────────────────────────────────────────────────

# Comparing two PROMPTING STRATEGIES on the same model (Gemini 3.1 Flash Lite):
# - "gemini"          → Advanced: role-play + few-shot examples + tone hints
# - "gemini_baseline" → Baseline: zero-shot, role-play system prompt only
MODELS = ["gemini", "gemini_baseline"]

# ── Results collector ──────────────────────────────────────────────────────────

results = []

# ── Main eval loop ─────────────────────────────────────────────────────────────

print("Starting evaluation...\n")

for model in MODELS:
    print(f"{'='*50}")
    print(f"Model: {model.upper()}")
    print(f"{'='*50}\n")

    for scenario in scenarios:
        sid   = scenario["id"]
        intent = scenario["intent"]
        facts  = scenario["facts"]
        tone   = scenario["tone"]
        reference = reference_map[sid]

        print(f"  Scenario {sid}: {intent[:50]}...")

        # ── Step 1: Generate email ─────────────────────────────────────────────
        try:
            generated = generate_mail(intent, facts, tone, model=model)
        except Exception as e:
            print(f"  ✗ Generation failed: {e}")
            continue

        # ── Step 2: Evaluate with all 3 metrics ───────────────────────────────
        try:
            scores = evaluate(
                facts=facts,
                tone=tone,
                generated_email=generated,
                reference_email=reference,
                generator_model=model
            )
        except Exception as e:
            print(f"  ✗ Evaluation failed: {e}")
            continue

        # ── Step 3: Collect result ─────────────────────────────────────────────
        result = {
            # Identifiers
            "scenario_id":   sid,
            "model":         model,
            "intent":        intent,
            "tone":          tone,

            # Generated output
            "generated_email": generated,

            # Metric 1: Fact Recall
            "fact_recall_score":         scores["fact_recall"]["score"],
            "fact_recall_justification": scores["fact_recall"]["justification"],

            # Metric 2: Tone Alignment
            "tone_alignment_score":         scores["tone_alignment"]["score"],
            "tone_alignment_justification": scores["tone_alignment"]["justification"],

            # Metric 3: Fluency (Hybrid)
            "fluency_score":         scores["fluency"]["score"],
            "fluency_llm_score":     scores["fluency"]["llm_score"],
            "fluency_rouge_l_score": scores["fluency"]["rouge_l_score"],
            "fluency_justification": scores["fluency"]["justification"],

            # Overall
            "overall_score": round(
                (
                    scores["fact_recall"]["score"] +
                    scores["tone_alignment"]["score"] +
                    scores["fluency"]["score"]
                ) / 3, 4
            ),

            # Meta
            "judge_model": scores["judge_model"],
        }

        results.append(result)

        print(f"  ✓ Fact Recall:    {result['fact_recall_score']}")
        print(f"  ✓ Tone Alignment: {result['tone_alignment_score']}")
        print(f"  ✓ Fluency:        {result['fluency_score']}")
        print(f"  ✓ Overall:        {result['overall_score']}\n")

        # ── Rate limiting ──────────────────────────────────────────────────────
        # 20s gap + 5s × 2 sleeps inside evaluate() = ~32s per scenario.
        # Gemini 3.1 Flash Lite judge calls hit ~5-6 RPM, well under 15 RPM.
        time.sleep(20)

# ── Save results ───────────────────────────────────────────────────────────────

os.makedirs("results", exist_ok=True)

# ── JSON output ────────────────────────────────────────────────────────────────
with open("results/eval_report.json", "w") as f:
    json.dump(results, f, indent=2)

print("✓ Saved results/eval_report.json")

# ── CSV output ─────────────────────────────────────────────────────────────────
csv_fields = [
    "scenario_id", "model", "intent", "tone",
    "fact_recall_score", "tone_alignment_score",
    "fluency_score", "fluency_llm_score", "fluency_rouge_l_score",
    "overall_score", "judge_model",
    "fact_recall_justification",
    "tone_alignment_justification",
    "fluency_justification",
]

with open("results/eval_report.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=csv_fields)
    writer.writeheader()
    for row in results:
        writer.writerow({k: row[k] for k in csv_fields})

print("✓ Saved results/eval_report.csv")

# ── Summary statistics ─────────────────────────────────────────────────────────

print("\n" + "="*50)
print("SUMMARY")
print("="*50)

for model in MODELS:
    model_results = [r for r in results if r["model"] == model]

    if not model_results:
        continue

    avg_fact_recall    = round(sum(r["fact_recall_score"]    for r in model_results) / len(model_results), 4)
    avg_tone_alignment = round(sum(r["tone_alignment_score"] for r in model_results) / len(model_results), 4)
    avg_fluency        = round(sum(r["fluency_score"]        for r in model_results) / len(model_results), 4)
    avg_overall        = round(sum(r["overall_score"]        for r in model_results) / len(model_results), 4)

    print(f"\n{model.upper()}")
    print(f"  Avg Fact Recall:    {avg_fact_recall}")
    print(f"  Avg Tone Alignment: {avg_tone_alignment}")
    print(f"  Avg Fluency:        {avg_fluency}")
    print(f"  Avg Overall:        {avg_overall}")

print("\nEvaluation complete.")