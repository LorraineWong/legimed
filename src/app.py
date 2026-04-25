import html as html_module
import json
from typing import Any, List, Optional

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


def _e(v: Any) -> str:
    return html_module.escape(str(v), quote=True) if v is not None else ""


def _is_food(substance: str) -> bool:
    words = set(substance.lower().replace("-", " ").split())
    return not bool(words & DRUG_KEYWORDS)


def _csv(v: Optional[str]) -> List[str]:
    return [x.strip() for x in v.split(",") if x.strip()] if v else []


def _status(type_: str, msg: str) -> str:
    s = {
        "success": ("background:#ECFDF5;border:1px solid #A7F3D0;color:#065F46;", "✅"),
        "warning": ("background:#FFFBEB;border:1px solid #FCD34D;color:#92400E;", "⚠️"),
        "error":   ("background:#FEF2F2;border:1px solid #FCA5A5;color:#991B1B;", "❌"),
        "info":    ("background:#EFF6FF;border:1px solid #BFDBFE;color:#1E40AF;", "ℹ️"),
    }
    st, icon = s.get(type_, s["error"])
    return f'<div style="{st}border-radius:12px;padding:10px 14px;font-size:13px;line-height:1.5;margin:6px 0;">{icon} {msg}</div>'


def format_html_output(drug_info, personal_summary: str) -> str:
    sev_border = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#10B981"}
    sev_tag_bg = {"HIGH": "#FEE2E2", "MEDIUM": "#FEF3C7", "LOW": "#D1FAE5"}
    sev_text   = {"HIGH": "#991B1B", "MEDIUM": "#92400E", "LOW": "#065F46"}
    sev_tag    = {"HIGH": "Emergency", "MEDIUM": "Call doctor", "LOW": "Monitor"}
    food_bg    = {"avoid": "#FEE2E2", "caution": "#FEF3C7", "ok": "#D1FAE5"}
    food_tc    = {"avoid": "#991B1B", "caution": "#92400E", "ok": "#065F46"}
    food_icon  = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    drug_name   = _e(getattr(drug_info, "drug_name", "Unknown"))
    active      = _e(getattr(drug_info, "active_ingredient", ""))
    drug_class  = _e(getattr(drug_info, "drug_class", ""))

    parts = [
        '<div style="font-family:-apple-system,BlinkMacSystemFont,\'Segoe UI\',sans-serif;'
        'background:#F7FAFC;border-radius:20px;padding:14px;color:#1A202C;">',

        # Header
        '<div style="background:linear-gradient(135deg,#00A878,#047857);'
        'border-radius:16px;padding:20px;margin-bottom:12px;color:#fff;">',
        '<div style="font-size:10px;font-weight:800;opacity:0.8;text-transform:uppercase;'
        'letter-spacing:0.08em;margin-bottom:6px;">Based on official drug label</div>',
        f'<div style="font-size:22px;font-weight:800;color:#fff;line-height:1.2;">{drug_name}</div>',
        f'<div style="font-size:12px;opacity:0.9;margin-top:4px;color:#fff;">{active}</div>',
        (f'<div style="display:inline-block;margin-top:8px;background:rgba(255,255,255,0.18);'
         f'border:1px solid rgba(255,255,255,0.25);padding:3px 10px;border-radius:999px;'
         f'font-size:11px;font-weight:600;color:#fff;">{drug_class}</div>' if drug_class else ""),
        '</div>',
    ]

    def card(content: str, bg="#FFFFFF", border="#E2E8F0", extra="") -> str:
        return (f'<div style="background:{bg};border:1px solid {border};'
                f'border-radius:16px;padding:14px 16px;margin-bottom:10px;'
                f'box-shadow:0 1px 6px rgba(0,0,0,0.06);{extra}">{content}</div>')

    def slabel(t: str, color="#00A878") -> str:
        return (f'<div style="font-size:10px;font-weight:800;color:{color};'
                f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:10px;">{t}</div>')

    # Summary — max 2 sentences already handled by personalise.py
    if personal_summary:
        parts.append(card(
            slabel("📋 Your Summary") +
            f'<div style="font-size:13px;color:#1A202C;line-height:1.75;'
            f'background:#ECFDF5;border-radius:10px;padding:12px;'
            f'border-left:3px solid #00A878;">{_e(personal_summary)}</div>'
        ))

    # When to take
    time_slots = {"morning": ("🌅", "Morning"), "afternoon": ("☀️", "Afternoon"),
                  "evening": ("🌆", "Evening"), "bedtime": ("🌙", "Bedtime")}
    dosage = getattr(drug_info, "dosage_instructions", []) or []
    dose_map = {getattr(d, "time_of_day", ""): d for d in dosage}
    grid = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">'
    for slot, (icon, label) in time_slots.items():
        d = dose_map.get(slot)
        if d:
            amt = _e(getattr(d, "amount", "") or "—")
            food = "With food" if getattr(d, "with_food", False) else "Without food"
            grid += (f'<div style="background:#ECFDF5;border:1px solid #A7F3D0;'
                     f'border-radius:10px;padding:8px 4px;text-align:center;">'
                     f'<div style="font-size:16px;">{icon}</div>'
                     f'<div style="font-size:9px;color:#4A5568;margin-top:2px;">{label}</div>'
                     f'<div style="font-size:11px;font-weight:800;color:#065F46;margin-top:2px;">{amt}</div>'
                     f'<div style="font-size:9px;color:#6B7280;">{food}</div></div>')
        else:
            grid += (f'<div style="background:#F1F5F9;border-radius:10px;'
                     f'padding:8px 4px;text-align:center;">'
                     f'<div style="font-size:16px;opacity:0.2;">{icon}</div>'
                     f'<div style="font-size:9px;color:#94A3B8;margin-top:2px;">{label}</div>'
                     f'<div style="font-size:12px;color:#CBD5E1;margin-top:2px;">—</div></div>')
    grid += '</div>'
    parts.append(card(slabel("⏰ When to Take") + grid))

    # Side effects — max 4, sorted by severity
    side_effects = getattr(drug_info, "side_effects", []) or []
    if side_effects:
        sorted_se = sorted(
            side_effects[:8],
            key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(getattr(x, "severity", ""), 3)
        )
        rows = ""
        for se in sorted_se[:4]:
            sev = getattr(se, "severity", "LOW") or "LOW"
            border = sev_border.get(sev, "#CBD5E1")
            tag_bg = sev_tag_bg.get(sev, "#F1F5F9")
            tag_tc = sev_text.get(sev, "#334155")
            tag    = sev_tag.get(sev, "Monitor")
            rows += (f'<div style="display:flex;align-items:flex-start;gap:8px;'
                     f'padding:9px 10px;border-radius:10px;'
                     f'border-left:3px solid {border};'
                     f'background:#F8FAFC;margin-bottom:6px;">'
                     f'<div style="flex:1;">'
                     f'<div style="font-size:12px;font-weight:700;color:#1A202C;">'
                     f'{_e(getattr(se, "name", ""))}</div>'
                     f'<div style="font-size:11px;color:#475569;line-height:1.5;margin-top:1px;">'
                     f'{_e(getattr(se, "description", ""))}</div></div>'
                     f'<span style="font-size:9px;padding:3px 7px;border-radius:999px;'
                     f'background:{tag_bg};color:{tag_tc};font-weight:700;'
                     f'white-space:nowrap;flex-shrink:0;">{tag}</span></div>')
        parts.append(card(slabel("⚡ Side Effects") + rows))

    # Food & drink — filter drugs
    food_items = [fi for fi in (getattr(drug_info, "food_interactions", []) or [])
                  if _is_food(getattr(fi, "substance", ""))]
    if food_items:
        chips = '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        for fi in food_items[:8]:
            action = getattr(fi, "action", "caution") or "caution"
            bg = food_bg.get(action, "#F1F5F9")
            tc = food_tc.get(action, "#334155")
            ic = food_icon.get(action, "⚠️")
            sub = _e(getattr(fi, "substance", ""))
            reason = _e(getattr(fi, "reason", ""))
            chips += (f'<span style="display:inline-flex;align-items:center;gap:4px;'
                      f'padding:6px 10px;border-radius:999px;background:{bg};'
                      f'font-size:12px;font-weight:600;color:{tc};" title="{reason}">'
                      f'{ic} {sub}</span>')
        chips += '</div>'
        parts.append(card(slabel("🍽 Food & Drink") + chips))
    else:
        parts.append(card(slabel("🍽 Food & Drink") +
                          '<p style="font-size:12px;color:#6B7280;margin:0;">'
                          'No specific food interactions found.</p>'))

    # Warnings — max 3, truncated
    warnings = getattr(drug_info, "warnings", []) or []
    if warnings:
        w_rows = ""
        for w in warnings[:3]:
            text = _e(getattr(w, "text", ""))
            if len(text) > 120:
                text = text[:120].rsplit(" ", 1)[0].rstrip(".,;") + "…"
            w_rows += (f'<div style="font-size:12px;color:#78350F;padding:5px 0;'
                       f'border-bottom:1px solid #FDE68A;line-height:1.6;">• {text}</div>')
        parts.append(card(
            slabel("⚠️ Warnings", "#B45309") + w_rows,
            bg="#FFFBEB", border="#FDE68A"
        ))

    # Emergency — max 3
    emergency = getattr(drug_info, "emergency_signs", []) or []
    if emergency:
        e_rows = "".join(
            f'<div style="font-size:12px;color:#7F1D1D;padding:3px 0;line-height:1.6;">• {_e(e)}</div>'
            for e in emergency[:3]
        )
        parts.append(card(
            slabel("🚨 Seek Help Immediately If:", "#B91C1C") + e_rows,
            bg="#FEF2F2", border="#FCA5A5"
        ))

    parts.append(
        '<div style="text-align:center;padding-top:8px;">'
        '<div style="font-size:10px;color:#9CA3AF;line-height:1.7;">'
        'Powered by Gemma 4 · NIH DailyMed<br>'
        'For reference only · Always consult your doctor or pharmacist'
        '</div></div></div>'
    )
    return "".join(parts)


def scan_image(pil_image, model, tokenizer, processor=None):
    if pil_image is None:
        return gr.update(), _status("error", "Please upload or capture an image first.")
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer, processor)
        if drug_name:
            return drug_name, _status(
                "success",
                f"Detected <strong>{_e(drug_name)}</strong> "
                f"<span style='color:#6B7280;font-size:11px;'>(via {_e(method)})</span><br>"
                "Edit if needed, then click Generate.")
        return "", _status("warning", "Could not detect drug name. Please type it below.")
    except Exception as exc:
        return gr.update(), _status("error", f"Scan error: {_e(str(exc))}")


def generate_guide(
    drug_name, age_group, sex,
    pregnant, breastfeeding,
    heart_condition, diabetes, hypertension, asthma,
    kidney_issue, liver_issue,
    other_conditions, allergies, other_medications,
    model, tokenizer,
):
    from extract import extract_drug_info_robust
    try:
        name = (drug_name or "").strip()
        if not name:
            return _status("error", "Please enter a medicine name first.")
        is_female = sex == "female"
        profile = UserProfile(
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
            allergies=_csv(allergies),
            other_medications=_csv(other_medications),
        )
        leaflet = get_drug_leaflet(name)
        if not leaflet:
            return _status("warning",
                f"'{_e(name)}' not found in DailyMed. "
                "Try the generic name, e.g. paracetamol instead of Panadol.")
        drug_info = extract_drug_info_robust(leaflet, model, tokenizer)
        drug_info = personalise(drug_info, profile)
        summary = generate_personal_summary(drug_info, profile)
        return format_html_output(drug_info, summary)
    except Exception as exc:
        return _status("error", f"Error: {_e(str(exc))}")


# ── Gradio UI ──────────────────────────────────────────────────────────────────

EMPTY_OUTPUT = """
<div style="text-align:center;padding:2.5rem 1rem;background:#fff;border-radius:16px;
     border:1.5px dashed #E2E8F0;color:#94A3B8;">
  <div style="font-size:32px;margin-bottom:8px;">🧾</div>
  <div style="font-size:15px;font-weight:700;color:#1A202C;margin-bottom:6px;">
    Your guide will appear here</div>
  <div style="font-size:13px;line-height:1.6;">
    Fill in your profile and medicine name, then tap Generate.</div>
</div>"""

LOADING_OUTPUT = """
<div style="text-align:center;padding:2.5rem 1rem;background:#fff;border-radius:16px;
     border:1px solid #E2E8F0;color:#1A202C;">
  <div style="font-size:13px;color:#00A878;font-weight:600;margin-bottom:4px;">
    ⏳ Generating your guide…</div>
  <div style="font-size:12px;color:#6B7280;">This takes about 45 seconds</div>
</div>"""

CSS = """
:root { color-scheme: light !important; }

*, *::before, *::after { box-sizing: border-box; }

html, body,
.gradio-container, .gradio-container > .main,
.gradio-container .wrap,
.gradio-container .app,
.gradio-container .svelte-1gfkn6j {
    background: #F7F8FA !important;
    color: #1A202C !important;
}

.gradio-container {
    max-width: 560px !important;
    min-width: 320px !important;
    margin: 0 auto !important;
    padding: 0 12px 48px !important;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
}

footer, .built-with, .api-docs { display: none !important; }

/* All Gradio blocks white */
.gradio-container .block,
.gradio-container .form,
.gradio-container .panel,
.gradio-container .wrap-inner,
.gradio-container .container,
.gradio-container fieldset,
.gradio-container .gap {
    background: #FFFFFF !important;
    border-color: #E2E8F0 !important;
    color: #1A202C !important;
}

/* Labels */
.gradio-container label span,
.gradio-container .label-wrap span,
.gradio-container .svelte-1b6s6s span {
    color: #1A202C !important;
    font-size: 12px !important;
    font-weight: 600 !important;
}

/* Inputs */
.gradio-container input[type=text],
.gradio-container input[type=number],
.gradio-container textarea {
    background: #F7F8FA !important;
    color: #1A202C !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 10px !important;
}
.gradio-container input::placeholder,
.gradio-container textarea::placeholder { color: #94A3B8 !important; }
.gradio-container input:focus,
.gradio-container textarea:focus {
    border-color: #00A878 !important;
    background: #FFFFFF !important;
    outline: none !important;
}

/* Radio & checkbox labels */
.gradio-container .radio-wrap,
.gradio-container .checkbox-wrap,
.gradio-container [data-testid="checkbox"],
.gradio-container [data-testid="radio"] {
    background: #FFFFFF !important;
    border: 1.5px solid #E2E8F0 !important;
    border-radius: 10px !important;
    color: #1A202C !important;
    padding: 6px 10px !important;
}

.gradio-container input[type=radio],
.gradio-container input[type=checkbox] {
    accent-color: #00A878 !important;
}

/* Primary button */
.gradio-container button.primary,
.gradio-container button[variant="primary"],
.gradio-container .primary > button {
    background: linear-gradient(135deg, #00A878, #047857) !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 14px !important;
    font-weight: 700 !important;
    font-size: 15px !important;
    box-shadow: 0 4px 14px rgba(0,168,120,0.25) !important;
    padding: 13px 20px !important;
}

/* Secondary button */
.gradio-container button.secondary,
.gradio-container button[variant="secondary"],
.gradio-container .secondary > button {
    background: #FFFFFF !important;
    color: #1A202C !important;
    border: 1.5px solid #CBD5E1 !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
}
.gradio-container button.secondary:hover,
.gradio-container button[variant="secondary"]:hover {
    border-color: #00A878 !important;
    color: #047857 !important;
}

/* Image upload area */
.gradio-container .upload-container,
.gradio-container [data-testid="image"],
.gradio-container .image-container {
    background: #F7F8FA !important;
    border: 2px dashed #B2F5EA !important;
    border-radius: 14px !important;
}

/* Accordion */
.gradio-container .accordion,
.gradio-container details {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 12px !important;
}
.gradio-container summary {
    color: #1A202C !important;
    font-weight: 600 !important;
    font-size: 13px !important;
}

/* Group/card */
.gradio-container .gr-group {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    padding: 14px !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.06) !important;
    margin-bottom: 12px !important;
}

.step-hdr {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
}
.step-num {
    width: 22px; height: 22px;
    border-radius: 50%;
    background: #00A878;
    color: #fff;
    font-size: 11px; font-weight: 800;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
}
.step-title { font-size: 14px; font-weight: 700; color: #1A202C; }
.step-sub { font-size: 11px; color: #6B7280; margin-top: 1px; }
"""


def build_demo(model, tokenizer, processor=None):

    def _scan(pil_image):
        return scan_image(pil_image, model, tokenizer, processor)

    def _generate(
        drug_name, age_group, sex,
        pregnant, breastfeeding,
        heart_condition, diabetes, hypertension, asthma,
        kidney_issue, liver_issue,
        other_conditions, allergies, other_medications,
    ):
        return generate_guide(
            drug_name, age_group, sex,
            pregnant, breastfeeding,
            heart_condition, diabetes, hypertension, asthma,
            kidney_issue, liver_issue,
            other_conditions, allergies, other_medications,
            model, tokenizer,
        )

    with gr.Blocks(title="Legimed", css=CSS) as demo:

        # ── Header ───────────────────────────────────────────────────────
        gr.HTML("""
        <div style="text-align:center;padding:24px 0 10px;">
          <div style="font-size:36px;">💊</div>
          <div style="font-size:26px;font-weight:800;color:#1A202C;
                      letter-spacing:-0.03em;margin-top:4px;">Legimed</div>
          <div style="font-size:13px;color:#6B7280;margin-top:6px;line-height:1.6;">
            Turn any medicine into a clear, personalised patient guide.<br>
            Powered by Gemma 4 · NIH DailyMed · Free &amp; offline.
          </div>
        </div>""")

        # ── Step 1: Profile ──────────────────────────────────────────────
        gr.HTML("""<div class="step-hdr" style="margin-top:16px;">
          <div class="step-num">1</div>
          <div>
            <div class="step-title">Your health profile</div>
            <div class="step-sub">Used to prioritise warnings. Nothing is stored.</div>
          </div>
        </div>""")

        with gr.Group():
            with gr.Row():
                age_group = gr.Radio(
                    choices=[("Child", "child"), ("Adult", "adult"), ("Elderly", "elderly")],
                    value="adult", label="Age group")
                sex = gr.Radio(
                    choices=[("Male", "male"), ("Female", "female"),
                             ("Not specified", "prefer_not_to_say")],
                    value="prefer_not_to_say", label="Sex")

            with gr.Accordion("Medical conditions (tap to expand)", open=False):
                with gr.Row():
                    pregnant       = gr.Checkbox(label="🤰 Pregnant", value=False)
                    breastfeeding  = gr.Checkbox(label="🍼 Breastfeeding", value=False)
                with gr.Row():
                    heart_condition = gr.Checkbox(label="❤️ Heart disease", value=False)
                    diabetes        = gr.Checkbox(label="🩸 Diabetes", value=False)
                with gr.Row():
                    hypertension   = gr.Checkbox(label="💉 Hypertension", value=False)
                    asthma         = gr.Checkbox(label="🫁 Asthma", value=False)
                with gr.Row():
                    kidney_issue   = gr.Checkbox(label="🫘 Kidney condition", value=False)
                    liver_issue    = gr.Checkbox(label="🫀 Liver condition", value=False)

            other_conditions = gr.Textbox(
                label="Other conditions",
                placeholder="e.g. G6PD deficiency, thyroid disorder",
                lines=1)
            allergies = gr.Textbox(
                label="Known allergies",
                placeholder="e.g. penicillin, sulfa, aspirin",
                lines=1)
            other_medications = gr.Textbox(
                label="Current medications",
                placeholder="e.g. aspirin, metformin, lisinopril",
                lines=1)

        # ── Step 2: Medication ───────────────────────────────────────────
        gr.HTML("""<div class="step-hdr" style="margin-top:4px;">
          <div class="step-num">2</div>
          <div>
            <div class="step-title">Your medication</div>
            <div class="step-sub">Scan the box or type the medicine name.</div>
          </div>
        </div>""")

        with gr.Group():
            image_input = gr.Image(
                type="pil",
                label="📷 Scan medicine box (optional)",
                sources=["upload", "webcam", "clipboard"],
                height=190)
            scan_btn    = gr.Button("🔍 Scan image", variant="secondary", size="sm")
            scan_status = gr.HTML(value="")
            drug_input  = gr.Textbox(
                label="💊 Medicine name",
                placeholder="e.g. metformin, ibuprofen, warfarin — or auto-filled after scan",
                lines=1)
            gr.HTML("""<div style="font-size:11px;color:#6B7280;margin-top:4px;
                                   background:#F7F8FA;border-radius:10px;padding:8px 10px;">
              💡 Tip: DailyMed works best with generic names.
              Try <strong style="color:#047857;">paracetamol</strong> instead of Panadol,
              or <strong style="color:#047857;">ibuprofen</strong> instead of Advil.
            </div>""")

        # ── Step 3: Generate ─────────────────────────────────────────────
        gr.HTML("""<div class="step-hdr" style="margin-top:4px;">
          <div class="step-num">3</div>
          <div>
            <div class="step-title">Generate your guide</div>
            <div class="step-sub">Review the medicine name, then tap the button.</div>
          </div>
        </div>""")

        generate_btn = gr.Button("Generate my guide →", variant="primary", size="lg")

        gr.HTML("""<div style="font-size:13px;font-weight:700;color:#1A202C;
                               margin:16px 0 6px;">Your guide</div>""")
        output = gr.HTML(value=EMPTY_OUTPUT)

        gr.HTML("""
        <div style="text-align:center;padding:16px 0 4px;">
          <div style="font-size:10px;color:#9CA3AF;line-height:1.7;">
            Gemma 4 · NIH DailyMed · Apache 2.0 ·
            <a href="https://github.com/LorraineWong/legimed"
               style="color:#00A878;text-decoration:none;font-weight:600;">GitHub</a>
          </div>
        </div>""")

        # ── Events ───────────────────────────────────────────────────────
        scan_btn.click(
            fn=lambda: (gr.update(interactive=False),
                        _status("info", "Scanning image…")),
            inputs=None, outputs=[scan_btn, scan_status], queue=False
        ).then(
            fn=_scan,
            inputs=[image_input],
            outputs=[drug_input, scan_status]
        ).then(
            fn=lambda: gr.update(interactive=True),
            inputs=None, outputs=[scan_btn], queue=False
        )

        GEN_INPUTS = [
            drug_input, age_group, sex,
            pregnant, breastfeeding,
            heart_condition, diabetes, hypertension, asthma,
            kidney_issue, liver_issue,
            other_conditions, allergies, other_medications,
        ]

        generate_btn.click(
            fn=lambda: LOADING_OUTPUT,
            inputs=None, outputs=output, queue=False
        ).then(
            fn=_generate,
            inputs=GEN_INPUTS,
            outputs=output
        )

    return demo
