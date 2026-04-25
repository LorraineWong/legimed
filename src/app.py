import html
import json
from typing import Any, Dict, List, Optional

import gradio as gr

from dailymed import get_drug_leaflet
from personalise import personalise, generate_personal_summary
from schema import UserProfile
from vision import image_to_drug_name


DRUG_KEYWORDS = {
    "drug", "drugs", "medication", "medications", "medicine", "medicines",
    "maoi", "maois", "inhibitor", "inhibitors", "nsaid", "nsaids",
    "antibiotic", "antibiotics", "supplement", "supplements",
    "containing", "products", "anticoagulant", "anticoagulants",
    "antidepressant", "antidepressants", "sedative", "sedatives",
    "prescription", "otc", "tablet", "tablets", "capsule", "capsules",
}


DEFAULT_OUTPUT_HTML = """
<div class="empty-state">
  <div class="empty-icon">🧾</div>
  <div class="empty-title">Your medication guide will appear here</div>
  <div class="empty-copy">Enter a medicine name or scan a package, then generate a personalized guide.</div>
</div>
"""


LOADING_HTML = """
<div class="loading-card">
  <div class="loading-spinner"></div>
  <div class="loading-title">Generating your guide...</div>
  <div class="loading-copy">This may take around 30–60 seconds on Colab.</div>
</div>
"""


def _escape(value: Any) -> str:
    """Escape user/model text before inserting it into HTML."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _is_food(substance: str) -> bool:
    words = set(substance.lower().replace("-", " ").split())
    return not bool(words & DRUG_KEYWORDS)


def _split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _status_html(type_: str, msg: str) -> str:
    styles = {
        "success": ("status-success", "✅"),
        "warning": ("status-warning", "⚠️"),
        "error": ("status-error", "❌"),
        "info": ("status-info", "ℹ️"),
    }
    class_name, icon = styles.get(type_, styles["error"])
    return f'<div class="status-box {class_name}">{icon} {msg}</div>'


def _safe_profile_from_inputs(
    age_group: str,
    sex: str,
    pregnant: bool,
    breastfeeding: bool,
    heart_condition: bool,
    diabetes: bool,
    hypertension: bool,
    asthma: bool,
    kidney_issue: bool,
    liver_issue: bool,
    other_conditions: str,
    allergies: str,
    other_medications: str,
) -> UserProfile:
    """Build a validated UserProfile from Gradio inputs."""
    is_female = sex == "female"
    return UserProfile(
        age_group=age_group or "adult",
        sex=sex or "prefer_not_to_say",
        pregnant=bool(pregnant) and is_female,
        breastfeeding=bool(breastfeeding) and is_female,
        heart_condition=bool(heart_condition),
        diabetes=bool(diabetes),
        hypertension=bool(hypertension),
        asthma=bool(asthma),
        kidney_issue=bool(kidney_issue),
        liver_issue=bool(liver_issue),
        other_conditions=other_conditions or "",
        allergies=_split_csv(allergies),
        other_medications=_split_csv(other_medications),
    )


def format_html_output(drug_info, personal_summary: str) -> str:
    severity_border = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#10B981"}
    severity_tag_bg = {"HIGH": "#FEE2E2", "MEDIUM": "#FEF3C7", "LOW": "#D1FAE5"}
    severity_text = {"HIGH": "#991B1B", "MEDIUM": "#92400E", "LOW": "#065F46"}
    severity_tag = {"HIGH": "Emergency", "MEDIUM": "Call doctor", "LOW": "Monitor"}
    food_class = {"avoid": "food-avoid", "caution": "food-caution", "ok": "food-ok"}
    food_icon = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    drug_name = _escape(getattr(drug_info, "drug_name", "Unknown medicine"))
    active_ingredient = _escape(getattr(drug_info, "active_ingredient", ""))
    drug_class = _escape(getattr(drug_info, "drug_class", ""))

    html_parts = [
        '<div class="guide-shell">',
        '<section class="guide-hero">',
        '<div class="guide-kicker">Based on official drug label</div>',
        f'<h2>{drug_name}</h2>',
        f'<p>{active_ingredient}</p>',
        f'<span>{drug_class}</span>' if drug_class else "",
        '</section>',
    ]

    if personal_summary:
        html_parts.append(
            '<section class="guide-card summary-card">'
            '<div class="section-label">📋 Your summary</div>'
            f'<p>{_escape(personal_summary)}</p>'
            '</section>'
        )

    time_slots = {
        "morning": ("🌅", "Morning"),
        "afternoon": ("☀️", "Afternoon"),
        "evening": ("🌆", "Evening"),
        "bedtime": ("🌙", "Bedtime"),
    }
    dosage_instructions = getattr(drug_info, "dosage_instructions", []) or []
    dose_map = {getattr(d, "time_of_day", ""): d for d in dosage_instructions}

    slots_html = ['<div class="dose-grid">']
    for slot, (icon, label) in time_slots.items():
        d = dose_map.get(slot)
        if d:
            amount = _escape(getattr(d, "amount", "") or "—")
            food_note = "With food" if getattr(d, "with_food", False) else "Food not specified"
            slots_html.append(
                '<div class="dose-card active">'
                f'<div class="dose-icon">{icon}</div>'
                f'<div class="dose-label">{label}</div>'
                f'<div class="dose-amount">{amount}</div>'
                f'<div class="dose-food">{food_note}</div>'
                '</div>'
            )
        else:
            slots_html.append(
                '<div class="dose-card muted">'
                f'<div class="dose-icon">{icon}</div>'
                f'<div class="dose-label">{label}</div>'
                '<div class="dose-amount">—</div>'
                '</div>'
            )
    slots_html.append('</div>')
    html_parts.append(
        '<section class="guide-card">'
        '<div class="section-label">⏰ When to take</div>'
        + "".join(slots_html) +
        '</section>'
    )

    side_effects = getattr(drug_info, "side_effects", []) or []
    if side_effects:
        sorted_side_effects = sorted(
            side_effects[:8],
            key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(getattr(x, "severity", ""), 3),
        )
        rows = []
        for se in sorted_side_effects[:5]:
            severity = getattr(se, "severity", "LOW") or "LOW"
            border = severity_border.get(severity, "#CBD5E1")
            tag_bg = severity_tag_bg.get(severity, "#F1F5F9")
            tag_text = severity_text.get(severity, "#334155")
            tag = severity_tag.get(severity, "Monitor")
            rows.append(
                f'<div class="effect-row" style="border-left-color:{border};">'
                '<div class="effect-copy">'
                f'<strong>{_escape(getattr(se, "name", "Side effect"))}</strong>'
                f'<p>{_escape(getattr(se, "description", ""))}</p>'
                '</div>'
                f'<span style="background:{tag_bg};color:{tag_text};">{tag}</span>'
                '</div>'
            )
        html_parts.append(
            '<section class="guide-card">'
            '<div class="section-label">⚡ Side effects</div>'
            + "".join(rows) +
            '</section>'
        )

    food_items = [fi for fi in (getattr(drug_info, "food_interactions", []) or []) if _is_food(getattr(fi, "substance", ""))]
    if food_items:
        chips = ['<div class="food-chip-wrap">']
        for fi in food_items[:8]:
            action = getattr(fi, "action", "caution") or "caution"
            chip_class = food_class.get(action, "food-caution")
            icon = food_icon.get(action, "⚠️")
            substance = _escape(getattr(fi, "substance", ""))
            reason = _escape(getattr(fi, "reason", ""))
            chips.append(f'<span class="food-chip {chip_class}" title="{reason}">{icon} {substance}</span>')
        chips.append('</div>')
        food_content = "".join(chips)
    else:
        food_content = '<p class="muted-copy">No specific food interactions found in the label.</p>'
    html_parts.append(
        '<section class="guide-card">'
        '<div class="section-label">🍽 Food & drink</div>'
        + food_content +
        '</section>'
    )

    warnings = getattr(drug_info, "warnings", []) or []
    if warnings:
        warning_rows = []
        for w in warnings[:4]:
            text = _escape(getattr(w, "text", ""))
            if len(text) > 170:
                text = text[:170].rsplit(" ", 1)[0].rstrip(".,;") + "…"
            warning_rows.append(f'<li>{text}</li>')
        html_parts.append(
            '<section class="guide-card warning-card">'
            '<div class="section-label amber">⚠️ Important warnings</div>'
            f'<ul>{"".join(warning_rows)}</ul>'
            '</section>'
        )

    emergency_signs = getattr(drug_info, "emergency_signs", []) or []
    if emergency_signs:
        emergency_rows = [f'<li>{_escape(e)}</li>' for e in emergency_signs[:4]]
        html_parts.append(
            '<section class="guide-card emergency-card">'
            '<div class="section-label red">🚨 Seek help immediately if</div>'
            f'<ul>{"".join(emergency_rows)}</ul>'
            '</section>'
        )

    html_parts.append(
        '<section class="guide-footer">'
        'Powered by Gemma · NIH DailyMed<br>'
        'For reference only. Always consult your doctor or pharmacist.'
        '</section>'
        '</div>'
    )
    return "".join(html_parts)


def scan_image(pil_image, model, tokenizer, processor=None):
    if pil_image is None:
        return gr.update(), _status_html("error", "Please upload or capture an image first.")
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer, processor)
        if drug_name:
            safe_drug_name = _escape(drug_name)
            return drug_name, _status_html(
                "success",
                f"Detected <strong>{safe_drug_name}</strong> "
                f"<span class='status-muted'>(via {_escape(method)})</span><br>"
                "Please confirm or edit the medicine name below."
            )
        return "", _status_html("warning", "I could not detect a medicine name. Please type it manually.")
    except Exception as exc:
        return gr.update(), _status_html("error", f"Scan error: {_escape(exc)}")


def generate_guide(
    drug_name: str,
    age_group: str,
    sex: str,
    pregnant: bool,
    breastfeeding: bool,
    heart_condition: bool,
    diabetes: bool,
    hypertension: bool,
    asthma: bool,
    kidney_issue: bool,
    liver_issue: bool,
    other_conditions: str,
    allergies: str,
    other_medications: str,
    model,
    tokenizer,
):
    from extract import extract_drug_info_robust

    try:
        clean_drug_name = (drug_name or "").strip()
        if not clean_drug_name:
            return _status_html("error", "Please enter a medicine name first.")

        profile = _safe_profile_from_inputs(
            age_group=age_group,
            sex=sex,
            pregnant=pregnant,
            breastfeeding=breastfeeding,
            heart_condition=heart_condition,
            diabetes=diabetes,
            hypertension=hypertension,
            asthma=asthma,
            kidney_issue=kidney_issue,
            liver_issue=liver_issue,
            other_conditions=other_conditions,
            allergies=allergies,
            other_medications=other_medications,
        )

        leaflet_text = get_drug_leaflet(clean_drug_name)
        if not leaflet_text:
            return _status_html(
                "warning",
                f"'{_escape(clean_drug_name)}' was not found in DailyMed. "
                "Try the generic name, for example paracetamol instead of Panadol."
            )

        drug_info = extract_drug_info_robust(leaflet_text, model, tokenizer)
        drug_info = personalise(drug_info, profile)
        summary = generate_personal_summary(drug_info, profile)
        return format_html_output(drug_info, summary)

    except Exception as exc:
        return _status_html("error", f"Error: {_escape(exc)}")


def build_demo(model, tokenizer, processor=None):
    def _scan(pil_image):
        return scan_image(pil_image, model, tokenizer, processor)

    def _generate(*args):
        return generate_guide(*args, model=model, tokenizer=tokenizer)

    css = """
    :root {
        color-scheme: light !important;
        --legi-bg: #F6F8FB;
        --legi-card: #FFFFFF;
        --legi-text: #0F172A;
        --legi-muted: #64748B;
        --legi-border: #E2E8F0;
        --legi-primary: #00A878;
        --legi-primary-dark: #047857;
        --legi-soft: #ECFDF5;
        --legi-shadow: 0 18px 45px rgba(15, 23, 42, 0.08);
    }

    html, body, .gradio-container, .main, .wrap, .app {
        background: var(--legi-bg) !important;
        color: var(--legi-text) !important;
    }

    .gradio-container {
        max-width: 980px !important;
        margin: 0 auto !important;
        padding: 22px 14px 44px !important;
        font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
    }

    footer, .api-docs, .built-with { display: none !important; }

    .legimed-hero {
        background: radial-gradient(circle at top left, #D1FAE5 0, transparent 34%),
                    linear-gradient(135deg, #FFFFFF 0%, #F8FAFC 100%);
        border: 1px solid rgba(226, 232, 240, 0.9);
        border-radius: 28px;
        padding: 28px;
        box-shadow: var(--legi-shadow);
        margin-bottom: 18px;
    }

    .legimed-brand {
        display: inline-flex;
        align-items: center;
        gap: 10px;
        padding: 7px 12px;
        border-radius: 999px;
        background: var(--legi-soft);
        color: var(--legi-primary-dark);
        font-weight: 750;
        font-size: 13px;
        margin-bottom: 14px;
    }

    .legimed-hero h1 {
        margin: 0;
        color: var(--legi-text);
        font-size: clamp(30px, 5vw, 48px);
        letter-spacing: -0.04em;
        line-height: 1.02;
    }

    .legimed-hero p {
        margin: 12px 0 0;
        color: var(--legi-muted);
        font-size: 15px;
        line-height: 1.7;
        max-width: 680px;
    }

    .step-card {
        background: var(--legi-card) !important;
        border: 1px solid var(--legi-border) !important;
        border-radius: 22px !important;
        padding: 18px !important;
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.06) !important;
        margin-bottom: 14px !important;
    }

    .step-heading {
        display: flex;
        align-items: center;
        gap: 10px;
        margin-bottom: 14px;
    }

    .step-num {
        width: 28px;
        height: 28px;
        border-radius: 999px;
        background: var(--legi-primary);
        color: white;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-weight: 800;
        font-size: 13px;
    }

    .step-heading strong {
        color: var(--legi-text);
        font-size: 15px;
    }

    .step-heading span {
        display: block;
        color: var(--legi-muted);
        font-size: 12px;
        margin-top: 2px;
    }

    .gradio-container label, .gradio-container .label-wrap span {
        color: var(--legi-text) !important;
        font-weight: 650 !important;
    }

    .gradio-container input,
    .gradio-container textarea,
    .gradio-container select,
    .gradio-container .wrap-inner,
    .gradio-container .input-container,
    .gradio-container .container,
    .gradio-container .block,
    .gradio-container .form,
    .gradio-container .panel {
        background: #FFFFFF !important;
        color: var(--legi-text) !important;
        border-color: var(--legi-border) !important;
    }

    .gradio-container input::placeholder,
    .gradio-container textarea::placeholder {
        color: #94A3B8 !important;
    }

    .gradio-container .radio label,
    .gradio-container .checkbox label,
    .gradio-container .checkboxgroup label {
        background: #FFFFFF !important;
        color: var(--legi-text) !important;
        border-color: var(--legi-border) !important;
        border-radius: 14px !important;
    }

    .gradio-container button.primary,
    .gradio-container .primary {
        background: linear-gradient(135deg, #00A878, #047857) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 16px !important;
        font-weight: 800 !important;
        box-shadow: 0 14px 28px rgba(0, 168, 120, 0.24) !important;
    }

    .gradio-container button.secondary,
    .gradio-container .secondary {
        background: #F8FAFC !important;
        color: var(--legi-text) !important;
        border: 1px solid var(--legi-border) !important;
        border-radius: 14px !important;
        font-weight: 700 !important;
    }

    .helper-note {
        color: var(--legi-muted);
        font-size: 12px;
        line-height: 1.6;
        margin-top: 8px;
    }

    .status-box {
        border-radius: 14px;
        padding: 12px 14px;
        font-size: 13px;
        line-height: 1.55;
        margin: 8px 0 4px;
    }
    .status-success { background:#ECFDF5; border:1px solid #A7F3D0; color:#065F46; }
    .status-warning { background:#FFFBEB; border:1px solid #FCD34D; color:#92400E; }
    .status-error { background:#FEF2F2; border:1px solid #FCA5A5; color:#991B1B; }
    .status-info { background:#EFF6FF; border:1px solid #BFDBFE; color:#1E40AF; }
    .status-muted { color:#64748B; font-size:12px; }

    .empty-state, .loading-card {
        background: #FFFFFF;
        border: 1.5px dashed var(--legi-border);
        border-radius: 22px;
        padding: 42px 22px;
        text-align: center;
        color: var(--legi-muted);
        box-shadow: 0 12px 30px rgba(15, 23, 42, 0.04);
    }
    .empty-icon { font-size: 34px; margin-bottom: 10px; }
    .empty-title, .loading-title { color: var(--legi-text); font-size: 16px; font-weight: 800; margin-bottom: 6px; }
    .empty-copy, .loading-copy { font-size: 13px; line-height: 1.6; }

    .loading-spinner {
        width: 34px;
        height: 34px;
        border: 3px solid #D1FAE5;
        border-top-color: var(--legi-primary);
        border-radius: 999px;
        margin: 0 auto 14px;
        animation: spin 0.9s linear infinite;
    }
    @keyframes spin { to { transform: rotate(360deg); } }

    .guide-shell {
        background: #F8FAFC;
        border-radius: 24px;
        padding: 12px;
        color: var(--legi-text);
    }
    .guide-hero {
        background: linear-gradient(135deg, #00A878, #047857);
        border-radius: 22px;
        padding: 22px;
        color: #FFFFFF;
        margin-bottom: 12px;
    }
    .guide-kicker { font-size: 11px; font-weight: 800; opacity: 0.85; text-transform: uppercase; letter-spacing: 0.08em; }
    .guide-hero h2 { margin: 8px 0 4px; font-size: 28px; line-height: 1.1; letter-spacing: -0.03em; color: #FFFFFF; }
    .guide-hero p { margin: 0; color: rgba(255,255,255,0.9); font-size: 13px; }
    .guide-hero span { display: inline-block; margin-top: 12px; padding: 5px 10px; border-radius: 999px; background: rgba(255,255,255,0.16); border: 1px solid rgba(255,255,255,0.24); font-size: 12px; font-weight: 700; color: #FFFFFF; }

    .guide-card {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 20px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 10px 24px rgba(15, 23, 42, 0.05);
    }
    .section-label { color: #047857; text-transform: uppercase; letter-spacing: 0.08em; font-size: 11px; font-weight: 850; margin-bottom: 12px; }
    .section-label.amber { color: #B45309; }
    .section-label.red { color: #B91C1C; }
    .summary-card p { margin: 0; color: #0F172A; line-height: 1.75; font-size: 14px; }

    .dose-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 8px; }
    .dose-card { border-radius: 16px; padding: 12px 8px; text-align: center; border: 1px solid #E2E8F0; }
    .dose-card.active { background: #ECFDF5; border-color: #A7F3D0; }
    .dose-card.muted { background: #F8FAFC; color: #94A3B8; }
    .dose-icon { font-size: 20px; margin-bottom: 4px; }
    .dose-label { font-size: 11px; color: #64748B; }
    .dose-amount { margin-top: 4px; color: #064E3B; font-size: 13px; font-weight: 850; }
    .dose-food { margin-top: 2px; color: #64748B; font-size: 10px; }

    .effect-row {
        display: flex;
        gap: 10px;
        align-items: flex-start;
        background: #F8FAFC;
        border-left: 4px solid #CBD5E1;
        border-radius: 14px;
        padding: 12px;
        margin-bottom: 8px;
    }
    .effect-copy { flex: 1; min-width: 0; }
    .effect-copy strong { color: #0F172A; font-size: 13px; }
    .effect-copy p { color: #475569; font-size: 12px; line-height: 1.55; margin: 3px 0 0; }
    .effect-row span { flex-shrink: 0; border-radius: 999px; padding: 4px 8px; font-size: 10px; font-weight: 850; white-space: nowrap; }

    .food-chip-wrap { display: flex; flex-wrap: wrap; gap: 8px; }
    .food-chip { display: inline-flex; align-items: center; gap: 4px; padding: 7px 10px; border-radius: 999px; font-size: 12px; font-weight: 750; }
    .food-avoid { background: #FEE2E2; color: #991B1B; }
    .food-caution { background: #FEF3C7; color: #92400E; }
    .food-ok { background: #D1FAE5; color: #065F46; }
    .muted-copy { color: #64748B; font-size: 13px; margin: 0; }

    .warning-card { background: #FFFBEB; border-color: #FDE68A; }
    .emergency-card { background: #FEF2F2; border-color: #FCA5A5; }
    .guide-card ul { margin: 0; padding-left: 18px; }
    .guide-card li { color: #334155; line-height: 1.65; font-size: 13px; margin-bottom: 5px; }
    .emergency-card li { color: #7F1D1D; }
    .warning-card li { color: #78350F; }
    .guide-footer { color: #94A3B8; font-size: 11px; line-height: 1.7; text-align: center; padding: 8px 4px 2px; }

    @media (max-width: 720px) {
        .legimed-hero { padding: 22px; border-radius: 22px; }
        .dose-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    """

    with gr.Blocks(title="Legimed", css=css, theme=gr.themes.Soft(primary_hue="green", neutral_hue="slate")) as demo:
        gr.HTML(
            """
            <header class="legimed-hero">
              <div class="legimed-brand">💊 Legimed</div>
              <h1>Your medication, made legible.</h1>
              <p>
                Scan a medicine package or enter a drug name. Legimed uses NIH DailyMed and Gemma
                to turn official drug labels into a clearer, personalized patient guide.
              </p>
            </header>
            """
        )

        with gr.Row(equal_height=False):
            with gr.Column(scale=5, min_width=320):
                with gr.Group(elem_classes=["step-card"]):
                    gr.HTML(
                        """
                        <div class="step-heading">
                          <div class="step-num">1</div>
                          <div><strong>Health profile</strong><span>Used to prioritize warnings. Nothing is stored.</span></div>
                        </div>
                        """
                    )
                    with gr.Row():
                        age_group = gr.Radio(
                            choices=[("Child", "child"), ("Adult", "adult"), ("Elderly", "elderly")],
                            value="adult",
                            label="Age group",
                        )
                        sex = gr.Radio(
                            choices=[("Male", "male"), ("Female", "female"), ("Prefer not to say", "prefer_not_to_say")],
                            value="prefer_not_to_say",
                            label="Sex",
                        )

                    with gr.Accordion("Medical conditions", open=True):
                        with gr.Row():
                            pregnant = gr.Checkbox(label="Pregnant", value=False)
                            breastfeeding = gr.Checkbox(label="Breastfeeding", value=False)
                        with gr.Row():
                            heart_condition = gr.Checkbox(label="Heart condition", value=False)
                            diabetes = gr.Checkbox(label="Diabetes", value=False)
                        with gr.Row():
                            hypertension = gr.Checkbox(label="Hypertension", value=False)
                            asthma = gr.Checkbox(label="Asthma", value=False)
                        with gr.Row():
                            kidney_issue = gr.Checkbox(label="Kidney issue", value=False)
                            liver_issue = gr.Checkbox(label="Liver issue", value=False)

                    other_conditions = gr.Textbox(
                        label="Other conditions",
                        placeholder="e.g. G6PD deficiency, stomach ulcer",
                        lines=1,
                    )
                    allergies = gr.Textbox(
                        label="Known allergies",
                        placeholder="e.g. penicillin, sulfa, aspirin",
                        lines=1,
                    )
                    other_medications = gr.Textbox(
                        label="Current medications",
                        placeholder="e.g. aspirin, metformin, lisinopril",
                        lines=1,
                    )

                with gr.Group(elem_classes=["step-card"]):
                    gr.HTML(
                        """
                        <div class="step-heading">
                          <div class="step-num">2</div>
                          <div><strong>Medication</strong><span>Scan the package or type the medicine name manually.</span></div>
                        </div>
                        """
                    )
                    image_input = gr.Image(
                        type="pil",
                        label="Scan medicine box or label (optional)",
                        sources=["upload", "webcam", "clipboard"],
                        height=210,
                    )
                    scan_btn = gr.Button("🔍 Scan image", variant="secondary", size="sm")
                    scan_status = gr.HTML(value="")
                    drug_input = gr.Textbox(
                        label="Medicine name",
                        placeholder="e.g. metformin, ibuprofen, warfarin",
                        lines=1,
                    )
                    gr.HTML(
                        """
                        <div class="helper-note">
                          Tip: DailyMed works best with US generic names. For example, try
                          <strong>acetaminophen</strong> or <strong>paracetamol</strong> instead of a local brand name.
                        </div>
                        """
                    )

                with gr.Group(elem_classes=["step-card"]):
                    gr.HTML(
                        """
                        <div class="step-heading">
                          <div class="step-num">3</div>
                          <div><strong>Generate guide</strong><span>Review the detected medicine name before generating.</span></div>
                        </div>
                        """
                    )
                    generate_btn = gr.Button("Generate my guide →", variant="primary", size="lg")

            with gr.Column(scale=6, min_width=340):
                with gr.Group(elem_classes=["step-card"]):
                    gr.HTML(
                        """
                        <div class="step-heading">
                          <div class="step-num">✓</div>
                          <div><strong>Your guide</strong><span>Personalized medication information appears below.</span></div>
                        </div>
                        """
                    )
                    output = gr.HTML(value=DEFAULT_OUTPUT_HTML)

        gr.HTML(
            """
            <div style="text-align:center;padding:14px 0 0;color:#94A3B8;font-size:11px;line-height:1.7;">
              Gemma · NIH DailyMed · Apache 2.0 ·
              <a href="https://github.com/LorraineWong/legimed" style="color:#047857;text-decoration:none;font-weight:700;">GitHub</a><br>
              For reference only. Always consult a qualified healthcare professional.
            </div>
            """
        )

        scan_btn.click(
            fn=lambda: (gr.update(interactive=False), _status_html("info", "Scanning image...")),
            inputs=None,
            outputs=[scan_btn, scan_status],
            queue=False,
        ).then(
            fn=_scan,
            inputs=[image_input],
            outputs=[drug_input, scan_status],
        ).then(
            fn=lambda: gr.update(interactive=True),
            inputs=None,
            outputs=[scan_btn],
            queue=False,
        )

        generate_inputs = [
            drug_input,
            age_group,
            sex,
            pregnant,
            breastfeeding,
            heart_condition,
            diabetes,
            hypertension,
            asthma,
            kidney_issue,
            liver_issue,
            other_conditions,
            allergies,
            other_medications,
        ]

        generate_btn.click(
            fn=lambda: LOADING_HTML,
            inputs=None,
            outputs=output,
            queue=False,
        ).then(
            fn=_generate,
            inputs=generate_inputs,
            outputs=output,
        )

    return demo
