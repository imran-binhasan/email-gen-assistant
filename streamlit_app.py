import streamlit as st
from app.generator import generate_mail

st.set_page_config(page_title="Email Generation Assistant", layout="wide")

st.title("Email Generation Assistant")
st.caption("Gemini 3.1 Flash Lite  ·  Advanced vs Baseline prompt comparison  ·  Role-playing + Few-shot + Tone hints")

col_input, col_output = st.columns([1, 1], gap="large")

with col_input:
    st.subheader("Compose")

    intent = st.text_input(
        "Intent",
        placeholder="e.g., Follow up on a job application submitted 2 weeks ago",
    )

    facts_raw = st.text_area(
        "Key Facts  (one per line)",
        height=160,
        placeholder="Applied for Senior Backend Engineer role\nSubmitted on June 2nd\nHave 4 years NestJS experience\nAvailable for interview any time this week",
    )

    tone_options = [
        "Formal, confident",
        "Apologetic, professional",
        "Casual, persuasive",
        "Formal, respectful",
        "Firm but polite",
        "Empathetic, constructive",
        "Enthusiastic, professional",
        "Urgent, direct",
        "Formal, humble",
        "Assertive, professional",
        "Custom…",
    ]
    tone_choice = st.selectbox("Tone", tone_options)
    if tone_choice == "Custom…":
        tone = st.text_input("Custom tone", placeholder="e.g., Warm, encouraging")
    else:
        tone = tone_choice

    model = st.radio(
        "Prompting Strategy",
        ["gemini", "gemini_baseline"],
        format_func=lambda x: "Advanced (few-shot + tone hints)" if x == "gemini" else "Baseline (zero-shot)",
        horizontal=True,
    )

    generate_btn = st.button("Generate Email", type="primary", use_container_width=True)

with col_output:
    st.subheader("Generated Email")

    if generate_btn:
        errors = []
        if not intent.strip():
            errors.append("Intent is required.")
        if not facts_raw.strip():
            errors.append("At least one fact is required.")
        if not tone.strip():
            errors.append("Tone is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            facts = [f.strip() for f in facts_raw.strip().splitlines() if f.strip()]
            model_label = "Advanced prompt" if model == "gemini" else "Baseline prompt"

            with st.spinner(f"Generating with {model_label}…"):
                try:
                    email = generate_mail(intent, facts, tone, model=model)
                    st.text_area(
                        label="email_output",
                        value=email,
                        height=480,
                        label_visibility="collapsed",
                    )
                    st.success(f"Generated using {model_label}")

                    st.download_button(
                        label="Download .txt",
                        data=email,
                        file_name="generated_email.txt",
                        mime="text/plain",
                    )
                except Exception as exc:
                    st.error(f"Generation failed: {exc}")
    else:
        st.info("Fill in the fields on the left and click **Generate Email**.")

with st.expander("How the prompting works"):
    st.markdown("""
**Techniques used:**

1. **Role-Playing** — The system prompt establishes the model as *"an expert professional email writer with 15 years of experience."*
   This anchors tone and quality from the first token.

2. **Few-Shot Examples** — Two complete example emails (formal/confident and urgent/direct) are injected before the task.
   They demonstrate the exact output format and quality expected.

3. **Explicit Hard Rules** — The system prompt lists specific rules the model must never break:
   no hallucinated facts, no ignored facts, no meta-commentary, always start with `Subject:`.

**Evaluation:**
A single Gemini 3.1 Flash Lite judge scores both strategies using 3 custom metrics: Fact Recall, Tone Alignment, and Hybrid Fluency (LLM score + ROUGE-L). A consistent judge improves score comparability across strategies.
""")
