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


def _is_food(substance: str) -> bool:
    words = set(substance.lower().replace("-", " ").split())
    return not bool(words & DRUG_KEYWORDS)


def format_html_output(drug_info, personal_summary) -> str:
    severity_border = {"HIGH": "#E53E3E", "MEDIUM": "#F6AD55", "LOW": "#38A169"}
    severity_tag_bg = {"HIGH": "#FEE2E2", "MEDIUM": "#FFF7E6", "LOW": "#E6FFFA"}
    severity_text   = {"HIGH": "#9B2C2C", "MEDIUM": "#B7791F", "LOW": "#276749"}
    severity_tag    = {"HIGH": "🚨 Emergency", "MEDIUM": "📞 Call doctor", "LOW": "👁 Monitor"}
    food_color = {"avoid": "#FEE2E2", "caution": "#FFF7E6", "ok": "#E6FFFA"}
    food_text  = {"avoid": "#9B2C2C", "caution": "#B7791F", "ok": "#276749"}
    food_icon  = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    def card(content, extra_style=""):
        return f"""<div style="background:#ffffff;border-radius:14px;
            box-shadow:0 1px 6px rgba(0,0,0,0.07);padding:14px 16px;
            margin-bottom:10px;{extra_style}">{content}</div>"""

    def section_label(label):
        return f"""<div style="font-size:10px;font-weight:700;color:#00A878;
            text-transform:uppercase;letter-spacing:0.08em;
            margin-bottom:10px;">{label}</div>"""

    html = """<div style="font-family:-apple-system,BlinkMacSystemFont,
        'Segoe UI',sans-serif;background:#F7FAFC;padding:14px;
        border-radius:16px;max-width:520px;margin:0 auto;color:#1A202C;">"""

    # Header card
    html += f"""<div style="background:linear-gradient(135deg,#00A878,#00875F);
        border-radius:14px;padding:18px;margin-bottom:10px;color:#ffffff;">
        <div style="font-size:21px;font-weight:800;line-height:1.2;color:#ffffff;">
            {drug_info.drug_name}</div>
        <div style="font-size:12px;opacity:0.9;margin-top:4px;color:#ffffff;">
            {drug_info.active_ingredient}</div>
        <div style="display:inline-block;margin-top:8px;background:rgba(255,255,255,0.2);
            border:1px solid rgba(255,255,255,0.3);padding:3px 10px;border-radius:999px;
            font-size:11px;font-weight:600;color:#ffffff;">{drug_info.drug_class}</div>
    </div>"""

    # Summary
    if personal_summary:
        html += card(
            section_label("📋 Your Summary") +
            f"""<div style="font-size:13px;color:#1A202C;line-height:1.7;
                background:#F0FFF8;border-radius:10px;padding:12px;
                border-left:3px solid #00A878;">{personal_summary}</div>"""
        )

    # When to take
    time_slots = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "bedtime": "🌙"}
    dose_map = {d.time_of_day: d for d in drug_info.dosage_instructions}
    slots_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">'
    for slot, icon in time_slots.items():
        d = dose_map.get(slot)
        if d:
            slots_html += f"""<div style="background:#E6FFFA;border:1px solid #8FDCC5;
                border-radius:10px;padding:8px 4px;text-align:center;">
                <div style="font-size:16px;">{icon}</div>
                <div style="font-size:9px;color:#4A5568;margin-top:2px;">{slot.capitalize()}</div>
                <div style="font-size:11px;font-weight:800;color:#065F46;margin-top:2px;">
                    {d.amount if d.amount else "—"}</div>
                <div style="font-size:9px;color:#4A5568;">
                    {"with food" if d.with_food else "no food"}</div>
            </div>"""
        else:
            slots_html += f"""<div style="background:#EDF2F7;border-radius:10px;
                padding:8px 4px;text-align:center;">
                <div style="font-size:16px;opacity:0.2;">{icon}</div>
                <div style="font-size:9px;color:#A0AEC0;margin-top:2px;">{slot.capitalize()}</div>
                <div style="font-size:12px;color:#A0AEC0;margin-top:2px;">—</div>
            </div>"""
    slots_html += "</div>"
    html += card(section_label("⏰ When to Take") + slots_html)

    # Side effects
    if drug_info.side_effects:
        se_html = ""
        sorted_se = sorted(
            drug_info.side_effects[:6],
            key=lambda x: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(x.severity, 3)
        )
        for se in sorted_se[:4]:
            border = severity_border.get(se.severity, "#CBD5E0")
            tc     = severity_text.get(se.severity, "#2D3748")
            tag    = severity_tag.get(se.severity, "Monitor")
            tag_bg = severity_tag_bg.get(se.severity, "#EDF2F7")
            se_html += f"""<div style="display:flex;align-items:flex-start;gap:8px;
                padding:9px 10px;border-radius:10px;border-left:3px solid {border};
                background:#FAFAFA;margin-bottom:6px;">
                <div style="flex:1;">
                    <div style="font-size:12px;font-weight:700;color:#1A202C;">{se.name}</div>
                    <div style="font-size:11px;color:{tc};line-height:1.5;margin-top:1px;">
                        {se.description}</div>
                </div>
                <div style="font-size:9px;padding:3px 7px;border-radius:999px;
                    background:{tag_bg};color:{tc};font-weight:700;
                    white-space:nowrap;flex-shrink:0;">{tag}</div>
            </div>"""
        html += card(section_label("⚡ Side Effects") + se_html)

    # Food & drink
    food_items = [fi for fi in drug_info.food_interactions if _is_food(fi.substance)]
    if food_items:
        fi_html = '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        for fi in food_items:
            bg   = food_color.get(fi.action, "#F4F7FB")
            tc   = food_text.get(fi.action, "#1A202C")
            icon = food_icon.get(fi.action, "")
            fi_html += f"""<div style="display:flex;align-items:center;gap:4px;
                padding:6px 10px;border-radius:999px;background:{bg};
                font-size:12px;font-weight:600;color:{tc};" title="{fi.reason}">
                {icon} {fi.substance}</div>"""
        fi_html += "</div>"
        html += card(section_label("🍽 Food & Drink") + fi_html)
    else:
        html += card(section_label("🍽 Food & Drink") +
            "<div style='font-size:12px;color:#718096;'>No specific food interactions found.</div>")

    # Warnings
    if drug_info.warnings:
        w_html = ""
        for w in drug_info.warnings[:3]:
            text = w.text
            if len(text) > 100:
                text = text[:100].rsplit(" ", 1)[0].rstrip(".,;") + "…"
            w_html += f"""<div style="font-size:12px;color:#744210;padding:4px 0;
                border-bottom:1px solid #FDE68A;line-height:1.6;">• {text}</div>"""
        html += f"""<div style="background:#FFFBF0;border-left:3px solid #F6AD55;
            border-radius:14px;box-shadow:0 1px 6px rgba(0,0,0,0.06);
            padding:14px 16px;margin-bottom:10px;">
            <div style="font-size:10px;font-weight:700;color:#B7791F;
                text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">
                ⚠️ Warnings</div>
            {w_html}</div>"""

    # Emergency
    if drug_info.emergency_signs:
        e_html = ""
        for e in drug_info.emergency_signs[:3]:
            e_html += f"""<div style="font-size:12px;color:#7F1D1D;
                padding:3px 0;line-height:1.6;">• {e}</div>"""
        html += f"""<div style="background:#FFF5F5;border:1px solid #FEB2B2;
            border-radius:14px;box-shadow:0 1px 6px rgba(0,0,0,0.06);
            padding:14px 16px;margin-bottom:10px;">
            <div style="font-size:10px;font-weight:800;color:#C53030;
                text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">
                🚨 Seek Help Immediately If:</div>
            {e_html}</div>"""

    html += """<div style="text-align:center;padding-top:6px;">
        <div style="font-size:10px;color:#A0AEC0;line-height:1.7;">
            Powered by Gemma 4 · NIH DailyMed<br>
            For reference only · Always consult your doctor or pharmacist
        </div></div></div>"""
    return html


def scan_image(pil_image, model, tokenizer, processor=None):
    if pil_image is None:
        return "", _status_html("error", "No image provided.")
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer, processor)
        if drug_name:
            return drug_name, _status_html("success",
                f"Detected: <strong>{drug_name}</strong> "
                f"<span style='font-size:11px;color:#718096;'>(via {method})</span><br>"
                f"<span style='font-size:11px;'>Edit if needed, then click Generate.</span>")
        else:
            return "", _status_html("warning", "Could not detect drug name. Please type it below.")
    except Exception as e:
        return "", _status_html("error", f"Scan error: {str(e)}")


def _status_html(type_, msg):
    styles = {
        "success": ("background:#F0FDF4;border:1px solid #6EE7B7;color:#065F46;", "✅"),
        "warning": ("background:#FEF3C7;border:1px solid #FCD34D;color:#92400E;", "⚠️"),
        "error":   ("background:#FEF2F2;border:1px solid #FEB2B2;color:#9B2C2C;", "❌"),
    }
    style, icon = styles.get(type_, styles["error"])
    return (f"<div style='{style}border-radius:10px;padding:10px 14px;"
            f"font-size:13px;margin-top:6px;'>{icon} {msg}</div>")


def generate_guide(drug_name, age_group, sex, pregnant, breastfeeding,
                   heart_condition, diabetes, hypertension, asthma,
                   kidney_issue, liver_issue, allergies, other_meds,
                   model, tokenizer):
    from extract import extract_drug_info_robust
    try:
        if not drug_name.strip():
            return _status_html("error", "Please enter a drug name first.")
        leaflet_text = get_drug_leaflet(drug_name.strip())
        if not leaflet_text:
            return _status_html("warning",
                f"'{drug_name}' not found in DailyMed. "
                f"Try the generic name (e.g. paracetamol instead of Panadol).")
        profile = UserProfile(
            age_group=age_group,
            pregnant=pregnant and sex == "female",
            breastfeeding=breastfeeding and sex == "female",
            heart_condition=heart_condition,
            diabetes=diabetes,
            hypertension=hypertension,
            asthma=asthma,
            kidney_issue=kidney_issue,
            liver_issue=liver_issue,
            allergies=[a.strip() for a in allergies.split(",") if a.strip()],
            other_medications=[m.strip() for m in other_meds.split(",") if m.strip()]
        )
        drug_info = extract_drug_info_robust(leaflet_text, model, tokenizer)
        drug_info = personalise(drug_info, profile)
        summary = generate_personal_summary(drug_info, profile)
        return format_html_output(drug_info, summary)
    except Exception as e:
        return _status_html("error", f"Error: {str(e)}")


def build_demo(model, tokenizer, processor=None):

    def _scan(pil_image):
        return scan_image(pil_image, model, tokenizer, processor)

    def _generate(drug_name, age_group, sex, pregnant, breastfeeding,
                  heart_condition, diabetes, hypertension, asthma,
                  kidney_issue, liver_issue, allergies, other_meds):
        return generate_guide(
            drug_name, age_group, sex, pregnant, breastfeeding,
            heart_condition, diabetes, hypertension, asthma,
            kidney_issue, liver_issue, allergies, other_meds,
            model, tokenizer
        )

    # Pure HTML/CSS UI — no Gradio theme dependency
    PAGE_CSS = """
    * { box-sizing: border-box; }
    body, .gradio-container, .main, .wrap, .app {
        background: #F7F8FA !important;
        color: #1A202C !important;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    }
    .gradio-container {
        max-width: 520px !important;
        min-width: 320px !important;
        margin: 0 auto !important;
        padding: 0 12px 40px !important;
        overflow-x: hidden !important;
    }
    footer { display: none !important; }
    .block, .form { background: #ffffff !important; }
    label > span { color: #1A202C !important; font-size: 13px !important; }
    input, textarea, select {
        background: #ffffff !important;
        color: #1A202C !important;
        border: 1.5px solid #E2E8F0 !important;
        border-radius: 10px !important;
    }
    input::placeholder, textarea::placeholder { color: #A0AEC0 !important; }
    .gr-button-primary {
        background: linear-gradient(135deg, #00A878, #00875F) !important;
        border: none !important;
        border-radius: 999px !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        font-size: 15px !important;
    }
    .gr-button-secondary {
        background: #ffffff !important;
        border: 1.5px solid #00A878 !important;
        border-radius: 999px !important;
        color: #00A878 !important;
        font-weight: 600 !important;
    }
    .gr-group, .gr-box {
        background: #ffffff !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 14px !important;
    }
    .gr-check-radio input { accent-color: #00A878 !important; }
    svg, .icon { color: #1A202C !important; }
    """

    def step_header(n, label):
        return f"""<div style="display:flex;align-items:center;gap:8px;
            margin:14px 0 8px;background:#F7F8FA;padding:2px 0;">
            <div style="width:22px;height:22px;border-radius:50%;background:#00A878;
                color:#ffffff;font-size:11px;font-weight:800;display:flex;
                align-items:center;justify-content:center;flex-shrink:0;">{n}</div>
            <div style="font-size:13px;font-weight:700;color:#1A202C;">{label}</div>
        </div>"""

    with gr.Blocks(title="Legimed", css=PAGE_CSS) as demo:

        gr.HTML("""<div style="text-align:center;padding:20px 0 8px;background:#F7F8FA;">
            <div style="font-size:34px;">💊</div>
            <div style="font-size:26px;font-weight:800;color:#1A202C;margin-top:2px;">Legimed</div>
            <div style="font-size:13px;color:#718096;margin-top:4px;">
                Your medication, made legible</div>
        </div>""")

        # Step 1: Profile
        gr.HTML(step_header(1, "Your health profile"))
        with gr.Group():
            with gr.Row():
                age_input = gr.Radio(
                    choices=["child", "adult", "elderly"],
                    value="adult", label="Age group")
                sex_input = gr.Radio(
                    choices=["male", "female"],
                    value="male", label="Sex")
            gr.HTML("<div style='font-size:11px;color:#718096;margin:8px 0 4px;"
                    "font-weight:600;padding:0 4px;'>Chronic conditions</div>")
            with gr.Row():
                heart_input  = gr.Checkbox(label="❤️ Heart disease")
                db_input     = gr.Checkbox(label="🩸 Diabetes")
            with gr.Row():
                bp_input     = gr.Checkbox(label="💉 Hypertension")
                asthma_input = gr.Checkbox(label="🫁 Asthma")
            with gr.Row():
                kidney_input = gr.Checkbox(label="🫘 Kidney condition")
                liver_input  = gr.Checkbox(label="🫀 Liver condition")
            with gr.Row():
                preg_input   = gr.Checkbox(label="🤰 Pregnant")
                bf_input     = gr.Checkbox(label="🍼 Breastfeeding")
            allergies_input = gr.Textbox(
                label="⚠️ Known allergies",
                placeholder="e.g. penicillin, sulfa, aspirin")
            meds_input = gr.Textbox(
                label="💊 Current medications",
                placeholder="e.g. aspirin, metformin, lisinopril")

        # Step 2: Medication
        gr.HTML(step_header(2, "Your medication"))
        with gr.Group():
            image_input = gr.Image(
                type="pil",
                label="📷 Scan medicine box (optional)",
                sources=["upload", "webcam", "clipboard"],
                height=180)
            scan_btn    = gr.Button("🔍 Scan image", variant="secondary", size="sm")
            scan_status = gr.HTML(value="")
            drug_input  = gr.Textbox(
                label="💊 Drug name",
                placeholder="Auto-filled after scan, or type here")

        # Step 3: Generate
        gr.HTML(step_header(3, "Generate your guide"))
        generate_btn = gr.Button("Generate my guide →", variant="primary", size="lg")

        gr.HTML("<div style='font-size:13px;font-weight:700;color:#1A202C;"
                "margin:14px 0 6px;'>Your guide</div>")
        output = gr.HTML(
            value="<div style='color:#718096;font-size:13px;padding:2rem 1rem;"
                  "text-align:center;background:#ffffff;border-radius:14px;"
                  "border:1.5px dashed #E2E8F0;'>"
                  "Complete the steps above to generate your guide.</div>")

        gr.HTML("""<div style="text-align:center;padding:16px 0 4px;">
            <div style="font-size:10px;color:#A0AEC0;line-height:1.6;">
                Gemma 4 · NIH DailyMed · Apache 2.0 ·
                <a href="https://github.com/LorraineWong/legimed"
                   style="color:#00A878;text-decoration:none;">GitHub</a>
            </div></div>""")

        # Events
        scan_btn.click(
            fn=lambda: (gr.update(interactive=False), ""),
            inputs=None, outputs=[scan_btn, scan_status], queue=False
        ).then(
            fn=_scan, inputs=[image_input], outputs=[drug_input, scan_status]
        ).then(
            fn=lambda: gr.update(interactive=True),
            inputs=None, outputs=[scan_btn], queue=False
        )

        generate_btn.click(
            fn=lambda: ("<div style='text-align:center;padding:2rem 1rem;"
                        "color:#00A878;font-size:13px;background:#ffffff;"
                        "border-radius:14px;'>⏳ Generating your guide…<br>"
                        "<span style='font-size:11px;color:#718096;'>"
                        "About 45 seconds</span></div>"),
            inputs=None, outputs=output, queue=False
        ).then(
            fn=_generate,
            inputs=[drug_input, age_input, sex_input, preg_input, bf_input,
                    heart_input, db_input, bp_input, asthma_input,
                    kidney_input, liver_input, allergies_input, meds_input],
            outputs=output
        )

    return demo
