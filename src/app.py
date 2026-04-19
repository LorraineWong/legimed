from __future__ import annotations

import textwrap

import gradio as gr

from dailymed import get_drug_leaflet
from extract import extract_drug_info_robust
from personalise import personalise
from schema import DrugInfo, Severity, UserProfile

_SEVERITY_EMOJI = {
    Severity.low: "🟢",
    Severity.moderate: "🟡",
    Severity.high: "🟠",
    Severity.critical: "🔴",
}

_MODEL = None
_TOKENIZER = None


def _load_model():
    global _MODEL, _TOKENIZER
    if _MODEL is None:
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_id = "google/gemma-3-1b-it"
        _TOKENIZER = AutoTokenizer.from_pretrained(model_id)
        _MODEL = AutoModelForCausalLM.from_pretrained(model_id, device_map="auto")
    return _MODEL, _TOKENIZER


def _format_drug_info(info: DrugInfo) -> str:
    lines: list[str] = []

    lines.append(f"# {info.drug_name}")
    if info.generic_name:
        lines.append(f"**Generic name:** {info.generic_name}")
    if info.drug_class:
        lines.append(f"**Drug class:** {info.drug_class}")

    if info.indications:
        lines.append("\n## Indications")
        for ind in info.indications:
            lines.append(f"- {ind}")

    if info.dosage_instructions:
        lines.append("\n## Dosage")
        for di in info.dosage_instructions:
            parts = [p for p in [di.route, di.dose, di.frequency] if p]
            lines.append(f"- {' | '.join(parts)}")
            if di.notes:
                lines.append(f"  _{di.notes}_")

    if info.warnings:
        lines.append("\n## Warnings")
        for w in info.warnings:
            badge = _SEVERITY_EMOJI.get(w.severity, "")
            lines.append(f"- {badge} **[{w.severity.value.upper()}]** {w.text}")

    if info.side_effects:
        lines.append("\n## Side Effects")
        for se in info.side_effects:
            badge = _SEVERITY_EMOJI.get(se.severity, "")
            freq = f" ({se.frequency})" if se.frequency else ""
            lines.append(f"- {badge} {se.effect}{freq}")

    if info.food_interactions:
        lines.append("\n## Food Interactions")
        for fi in info.food_interactions:
            reason = f" — {fi.reason}" if fi.reason else ""
            lines.append(f"- **{fi.action.value.replace('_', ' ').title()}** {fi.food_item}{reason}")

    if info.contraindications:
        lines.append("\n## Contraindications")
        for ci in info.contraindications:
            lines.append(f"- {ci}")

    if info.storage:
        lines.append(f"\n## Storage\n{info.storage}")

    return "\n".join(lines)


def run_pipeline(
    drug_name: str,
    age_group: str,
    pregnant: bool,
    kidney_impairment: bool,
    liver_impairment: bool,
    other_medications: str,
) -> str:
    if not drug_name.strip():
        return "Please enter a drug name."

    other_meds = [m.strip() for m in other_medications.split(",") if m.strip()]
    profile = UserProfile(
        age_group=age_group,
        pregnant=pregnant,
        kidney_impairment=kidney_impairment,
        liver_impairment=liver_impairment,
        other_medications=other_meds,
    )

    try:
        leaflet_text = get_drug_leaflet(drug_name.strip())
    except Exception as exc:
        return f"Could not retrieve leaflet: {exc}"

    try:
        model, tokenizer = _load_model()
        drug_info = extract_drug_info_robust(leaflet_text, model, tokenizer)
    except Exception as exc:
        return f"Extraction failed: {exc}"

    personalised = personalise(drug_info, profile)
    return _format_drug_info(personalised)


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Legimed — Medication Guide") as demo:
        gr.Markdown(
            textwrap.dedent("""\
            # Legimed
            **Personalised medication information powered by DailyMed + Gemma 3**

            Enter a drug name and your profile to receive a tailored summary of
            warnings, side effects, and food interactions.
            """)
        )

        with gr.Row():
            with gr.Column(scale=1):
                drug_input = gr.Textbox(
                    label="Drug name",
                    placeholder="e.g. metformin, ibuprofen, amoxicillin",
                )
                age_radio = gr.Radio(
                    choices=["child", "adult", "elderly"],
                    value="adult",
                    label="Age group",
                )
                pregnant_cb = gr.Checkbox(label="Pregnant or breastfeeding")
                kidney_cb = gr.Checkbox(label="Kidney impairment")
                liver_cb = gr.Checkbox(label="Liver impairment")
                other_meds_input = gr.Textbox(
                    label="Other medications (comma-separated)",
                    placeholder="e.g. warfarin, lisinopril",
                )
                submit_btn = gr.Button("Generate guide", variant="primary")

            with gr.Column(scale=2):
                output_md = gr.Markdown(label="Medication guide")

        submit_btn.click(
            fn=run_pipeline,
            inputs=[drug_input, age_radio, pregnant_cb, kidney_cb, liver_cb, other_meds_input],
            outputs=output_md,
        )

    return demo


if __name__ == "__main__":
    build_ui().launch()
