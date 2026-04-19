import gradio as gr
from dailymed import get_drug_leaflet
from personalise import personalise, generate_personal_summary
from schema import UserProfile
from vision import image_to_drug_name


def format_html_output(drug_info, personal_summary) -> str:
    """Format DrugInfo as a clean card-based HTML output."""

    severity_color = {"HIGH": "#FEE2E2", "MEDIUM": "#FEF3C7", "LOW": "#D1FAE5"}
    severity_text = {"HIGH": "#991B1B", "MEDIUM": "#92400E", "LOW": "#065F46"}
    severity_tag = {"HIGH": "Emergency", "MEDIUM": "Call doctor", "LOW": "Monitor"}
    severity_dot = {"HIGH": "#E24B4A", "MEDIUM": "#EF9F27", "LOW": "#1D9E75"}
    food_color = {"avoid": "#FEE2E2", "caution": "#FEF3C7", "ok": "#D1FAE5"}
    food_text = {"avoid": "#991B1B", "caution": "#92400E", "ok": "#065F46"}
    food_icon = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    html = f"""
    <div style="font-family:system-ui,-apple-system,sans-serif;background:#F0F4F8;padding:16px;border-radius:16px;">

      <div style="background:#fff;border-radius:12px;border:0.5px solid #E2EAF4;padding:14px 16px;margin-bottom:10px;display:flex;align-items:flex-start;justify-content:space-between;">
        <div>
          <div style="font-size:18px;font-weight:600;color:#0D1B2A;">{drug_info.drug_name}</div>
          <div style="font-size:11px;color:#9BA8B5;margin-top:2px;">Active ingredient: {drug_info.active_ingredient}</div>
        </div>
        <div style="font-size:11px;padding:4px 10px;border-radius:6px;background:#E1F5EE;color:#085041;font-weight:500;">{drug_info.drug_class}</div>
      </div>
    """

    if personal_summary:
        html += f"""
      <div style="background:#fff;border-radius:12px;border:0.5px solid #E2EAF4;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#1D9E75;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">Your personal summary</div>
        <div style="font-size:13px;color:#0D1B2A;line-height:1.6;padding:10px 12px;background:#F0FDF4;border-radius:8px;border-left:3px solid #1D9E75;">{personal_summary}</div>
      </div>
        """

    time_slots = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "bedtime": "🌙"}
    dose_map = {}
    food_map = {}
    for d in drug_info.dosage_instructions:
        dose_map[d.time_of_day] = d.amount
        food_map[d.time_of_day] = "with food" if d.with_food else "without food"

    html += """
      <div style="background:#fff;border-radius:12px;border:0.5px solid #E2EAF4;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#1D9E75;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:10px;">When to take</div>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">
    """
    for slot, icon in time_slots.items():
        dose = dose_map.get(slot)
        active = dose is not None
        bg = "#E1F5EE" if active else "#F4F7FB"
        border = "border:1px solid #9FE1CB;" if active else ""
        dose_text = f'<div style="font-size:11px;font-weight:600;color:#085041;margin-top:2px;">{dose}</div>' if active else '<div style="font-size:11px;color:#D1D9E0;margin-top:2px;">—</div>'
        note = f'<div style="font-size:9px;color:#6B7B8D;margin-top:1px;">{food_map.get(slot,"")}</div>' if active else ""
        html += f"""
          <div style="border-radius:8px;padding:8px 4px;text-align:center;background:{bg};{border}">
            <div style="font-size:14px;">{icon}</div>
            <div style="font-size:9px;color:#9BA8B5;margin-top:2px;">{slot.capitalize()}</div>
            {dose_text}
            {note}
          </div>
        """
    html += "</div></div>"

    if drug_info.side_effects:
        html += """
      <div style="background:#fff;border-radius:12px;border:0.5px solid #E2EAF4;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#1D9E75;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">Side effects</div>
        """
        for se in drug_info.side_effects:
            bg = severity_color.get(se.severity, "#F4F7FB")
            tc = severity_text.get(se.severity, "#0D1B2A")
            dot = severity_dot.get(se.severity, "#888")
            tag = severity_tag.get(se.severity, "Monitor")
            html += f"""
        <div style="display:flex;align-items:center;gap:8px;padding:7px 8px;border-radius:7px;background:{bg};margin-bottom:4px;">
          <div style="width:7px;height:7px;border-radius:50%;background:{dot};flex-shrink:0;"></div>
          <span style="font-size:12px;color:{tc};flex:1;"><strong>{se.name}</strong>: {se.description}</span>
          <span style="font-size:9px;padding:2px 6px;border-radius:4px;background:rgba(255,255,255,0.6);color:{tc};font-weight:600;">{tag}</span>
        </div>
            """
        html += "</div>"

    if drug_info.food_interactions:
        html += """
      <div style="background:#fff;border-radius:12px;border:0.5px solid #E2EAF4;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#1D9E75;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">Food &amp; drink</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">
        """
        for fi in drug_info.food_interactions:
            bg = food_color.get(fi.action, "#F4F7FB")
            tc = food_text.get(fi.action, "#0D1B2A")
            icon = food_icon.get(fi.action, "")
            html += f'<div style="display:flex;align-items:center;gap:4px;padding:5px 9px;border-radius:7px;background:{bg};font-size:11px;font-weight:500;color:{tc};" title="{fi.reason}">{icon} {fi.substance}</div>'
        html += "</div></div>"

    if drug_info.warnings:
        html += """
      <div style="background:#FFFBEB;border:0.5px solid #FCD34D;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#92400E;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">⚠ Warnings</div>
        """
        for w in drug_info.warnings:
            html += f'<div style="font-size:12px;color:#78350F;padding:3px 0;">· {w.text}</div>'
        html += "</div>"

    if drug_info.emergency_signs:
        html += """
      <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:12px;padding:14px 16px;margin-bottom:10px;">
        <div style="font-size:9px;font-weight:700;color:#991B1B;text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;">🚨 Emergency — seek help immediately if:</div>
        """
        for e in drug_info.emergency_signs:
            html += f'<div style="font-size:12px;color:#7F1D1D;padding:2px 0;">· {e}</div>'
        html += "</div>"

    html += """
      <div style="padding-top:10px;border-top:0.5px solid #E2EAF4;display:flex;justify-content:space-between;align-items:center;">
        <span style="font-size:10px;color:#9BA8B5;">Powered by Gemma 4 · Verified against NIH DailyMed · For reference only</span>
        <span style="font-size:10px;color:#9BA8B5;">Always consult your doctor or pharmacist</span>
      </div>
    </div>
    """
    return html


def run_legimed(drug_name, age_group, pregnant, kidney_issue,
                liver_issue, other_meds, model, tokenizer):
    """Main pipeline: drug name -> personalized guide."""
    from extract import extract_drug_info_robust

    try:
        if not drug_name.strip():
            return "<p style='color:#991B1B;padding:1rem;'>Please enter a drug name first.</p>"

        leaflet_text = get_drug_leaflet(drug_name.strip())
        if not leaflet_text:
            return f"<p style='color:#991B1B;padding:1rem;'>'{drug_name}' not found in DailyMed. Please check the spelling.</p>"

        other_meds_list = [m.strip() for m in other_meds.split(",") if m.strip()]
        profile = UserProfile(
            age_group=age_group,
            pregnant=pregnant,
            kidney_issue=kidney_issue,
            liver_issue=liver_issue,
            other_medications=other_meds_list
        )
        drug_info = extract_drug_info_robust(leaflet_text, model, tokenizer)
        drug_info = personalise(drug_info, profile)
        personal_summary = generate_personal_summary(drug_info, profile)
        return format_html_output(drug_info, personal_summary)

    except Exception as e:
        return f"<p style='color:#991B1B;padding:1rem;'>Something went wrong: {str(e)}</p>"


def run_legimed_from_image(pil_image, age_group, pregnant, kidney_issue,
                            liver_issue, other_meds, model, tokenizer):
    """
    Image input pipeline:
      1. Tesseract OCR extracts text from photo
      2. Heuristic guesses drug name from OCR text
      3. DailyMed fetches full leaflet text
      4. Gemma 4 extracts structured DrugInfo JSON (same as text tab)
      5. Personalisation engine re-prioritises warnings for user profile
    Gemma 4 is the core AI engine throughout. OCR is pre-processing only.
    Returns: (detected_drug_name: str, html_output: str)
    """
    from extract import extract_drug_info_robust

    if pil_image is None:
        return ("", "<p style='color:#991B1B;padding:1rem;'>Please upload a photo first.</p>")

    try:
        drug_name = image_to_drug_name(pil_image)
        if not drug_name.strip():
            return (
                "",
                "<p style='color:#991B1B;padding:1rem;'>Could not read drug name from image. "
                "Please type the drug name manually in the Name tab.</p>"
            )

        leaflet_text = get_drug_leaflet(drug_name)
        if not leaflet_text:
            return (
                drug_name,
                f"<p style='color:#92400E;padding:1rem;background:#FEF3C7;border-radius:8px;'>"
                f"Detected: <strong>{drug_name}</strong><br><br>"
                f"Not found in DailyMed. This may be a brand name — "
                f"please edit above and click <strong>Use this name</strong>.</p>"
            )

        other_meds_list = [m.strip() for m in other_meds.split(",") if m.strip()]
        profile = UserProfile(
            age_group=age_group,
            pregnant=pregnant,
            kidney_issue=kidney_issue,
            liver_issue=liver_issue,
            other_medications=other_meds_list
        )
        drug_info = extract_drug_info_robust(leaflet_text, model, tokenizer)
        drug_info = personalise(drug_info, profile)
        personal_summary = generate_personal_summary(drug_info, profile)
        return (drug_name, format_html_output(drug_info, personal_summary))

    except Exception as e:
        return ("", f"<p style='color:#991B1B;padding:1rem;'>Error: {str(e)}</p>")


def build_demo(model, tokenizer):
    """Build Gradio demo. Two tabs: type drug name / scan photo."""

    def _run_text(drug_name, age_group, pregnant, kidney_issue, liver_issue, other_meds):
        return run_legimed(drug_name, age_group, pregnant, kidney_issue,
                           liver_issue, other_meds, model, tokenizer)

    def _run_image(pil_image, age_group, pregnant, kidney_issue, liver_issue, other_meds):
        return run_legimed_from_image(pil_image, age_group, pregnant, kidney_issue,
                                      liver_issue, other_meds, model, tokenizer)

    def _run_override(drug_name, age_group, pregnant, kidney_issue, liver_issue, other_meds):
        return run_legimed(drug_name, age_group, pregnant, kidney_issue,
                           liver_issue, other_meds, model, tokenizer)

    with gr.Blocks(title="Legimed", theme=gr.themes.Soft()) as demo:
        gr.Markdown("""
        # Legimed — Your Medication, Made Legible
        *Turn any medication into a personalized guide · Powered by Gemma 4 · Offline · Free*
        """)

        with gr.Tabs():

            with gr.Tab("📝 Type drug name"):
                with gr.Row():
                    with gr.Column(scale=1):
                        gr.Markdown("### Drug")
                        drug_input = gr.Textbox(
                            label="Drug name",
                            placeholder="e.g. warfarin, metformin, amlodipine",
                            value="warfarin"
                        )
                        gr.Markdown("### Your profile")
                        age1 = gr.Radio(choices=["adult", "elderly"], value="adult", label="Age group")
                        preg1 = gr.Checkbox(label="Pregnant or breastfeeding")
                        kid1 = gr.Checkbox(label="Kidney condition")
                        liv1 = gr.Checkbox(label="Liver condition")
                        meds1 = gr.Textbox(
                            label="Other medications (comma separated)",
                            placeholder="e.g. metformin, atorvastatin"
                        )
                        submit_btn = gr.Button("Generate my guide", variant="primary", size="lg")
                    with gr.Column(scale=2):
                        gr.Markdown("### Your personalized guide")
                        output1 = gr.HTML(
                            value="<p style='color:#9BA8B5;padding:1rem;'>Enter a drug name and click <strong>Generate my guide</strong>.</p>"
                        )

                submit_btn.click(
                    fn=lambda: "<p style='color:#1D9E75;padding:1rem;'>⏳ Generating… (~45 seconds)</p>",
                    inputs=None, outputs=output1, queue=False
                ).then(
                    fn=_run_text,
                    inputs=[drug_input, age1, preg1, kid1, liv1, meds1],
                    outputs=output1
                )

            with gr.Tab("📷 Scan drug box"):
                gr.Markdown("""
                Take a clear photo of your **medication box or bottle label**.
                Legimed reads the drug name automatically, then generates your guide.
                """)
                with gr.Row():
                    with gr.Column(scale=1):
                        image_input = gr.Image(
                            type="pil",
                            label="Drug box or label photo",
                            sources=["upload", "webcam", "clipboard"],
                            height=260,
                        )
                        gr.Markdown("**Tips:** good lighting · full front face of box · text clearly visible")
                        gr.Markdown("### Your profile")
                        age2 = gr.Radio(choices=["adult", "elderly"], value="adult", label="Age group")
                        preg2 = gr.Checkbox(label="Pregnant or breastfeeding")
                        kid2 = gr.Checkbox(label="Kidney condition")
                        liv2 = gr.Checkbox(label="Liver condition")
                        meds2 = gr.Textbox(
                            label="Other medications (comma separated)",
                            placeholder="e.g. metformin, atorvastatin"
                        )
                        scan_btn = gr.Button("📷 Scan & generate guide", variant="primary", size="lg")

                    with gr.Column(scale=2):
                        gr.Markdown("### Detected drug name")
                        detected_name = gr.Textbox(
                            label="Detected drug name (edit if OCR was wrong)",
                            placeholder="Appears here after scanning",
                            interactive=True,
                        )
                        use_name_btn = gr.Button("✏️ Use this name", size="sm", variant="secondary")
                        gr.Markdown("### Your personalized guide")
                        output2 = gr.HTML(
                            value="<p style='color:#9BA8B5;padding:1rem;'>Upload a photo and click <strong>Scan & generate guide</strong>.</p>"
                        )

                scan_btn.click(
                    fn=lambda: ("", "<p style='color:#1D9E75;padding:1rem;'>📷 Reading image… (~60 seconds)</p>"),
                    inputs=None, outputs=[detected_name, output2], queue=False
                ).then(
                    fn=_run_image,
                    inputs=[image_input, age2, preg2, kid2, liv2, meds2],
                    outputs=[detected_name, output2]
                )

                use_name_btn.click(
                    fn=lambda: "<p style='color:#1D9E75;padding:1rem;'>⏳ Generating… (~45 seconds)</p>",
                    inputs=None, outputs=output2, queue=False
                ).then(
                    fn=_run_override,
                    inputs=[detected_name, age2, preg2, kid2, liv2, meds2],
                    outputs=output2
                )

        gr.Markdown("""
        ---
        *Legimed · Gemma 4 Good Hackathon 2026 · Apache 2.0 · [GitHub](https://github.com/LorraineWong/legimed)*
        """)

    return demo
