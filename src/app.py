import gradio as gr
from dailymed import get_drug_leaflet
from personalise import personalise, generate_personal_summary
from schema import UserProfile
from vision import image_to_drug_name, tesseract_status


def format_html_output(drug_info, personal_summary) -> str:
    severity_color = {"HIGH": "#FEE2E2", "MEDIUM": "#FEF3C7", "LOW": "#D1FAE5"}
    severity_text  = {"HIGH": "#991B1B", "MEDIUM": "#92400E", "LOW": "#065F46"}
    severity_tag   = {"HIGH": "🚨 Emergency", "MEDIUM": "📞 Call doctor", "LOW": "👁 Monitor"}
    severity_dot   = {"HIGH": "#E24B4A", "MEDIUM": "#EF9F27", "LOW": "#1D9E75"}
    food_color = {"avoid": "#FEE2E2", "caution": "#FEF3C7", "ok": "#D1FAE5"}
    food_text  = {"avoid": "#991B1B", "caution": "#92400E", "ok": "#065F46"}
    food_icon  = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    def section(label, content):
        return f"""
        <div style="background:#fff;border-radius:14px;border:1px solid #E8EDF2;
                    padding:16px;margin-bottom:12px;">
          <div style="font-size:10px;font-weight:700;color:#1D9E75;text-transform:uppercase;
                      letter-spacing:0.1em;margin-bottom:10px;">{label}</div>
          {content}
        </div>"""

    html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
                background:#F4F7FB;padding:14px;border-radius:18px;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#1D9E75,#0f7a5a);border-radius:14px;
                  padding:16px;margin-bottom:12px;color:#fff;">
        <div style="font-size:20px;font-weight:700;">{drug_info.drug_name}</div>
        <div style="font-size:12px;opacity:0.85;margin-top:3px;">
          {drug_info.active_ingredient} · {drug_info.drug_class}
        </div>
      </div>"""

    if personal_summary:
        html += section("📋 Your Summary", f"""
          <div style="font-size:13px;color:#1a2e1f;line-height:1.7;
                      background:#F0FDF4;border-radius:8px;padding:12px;
                      border-left:3px solid #1D9E75;">{personal_summary}</div>""")

    time_slots = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "bedtime": "🌙"}
    dose_map = {d.time_of_day: d for d in drug_info.dosage_instructions}
    slots_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;">'
    for slot, icon in time_slots.items():
        d = dose_map.get(slot)
        if d:
            slots_html += f"""
            <div style="background:#E8F8F2;border:1px solid #9FE1CB;border-radius:10px;
                        padding:10px 6px;text-align:center;">
              <div style="font-size:18px;">{icon}</div>
              <div style="font-size:9px;color:#6B8F7E;margin-top:3px;">{slot.capitalize()}</div>
              <div style="font-size:11px;font-weight:700;color:#085041;margin-top:3px;">
                {d.amount if d.amount else "—"}</div>
              <div style="font-size:9px;color:#6B8F7E;">
                {"with food" if d.with_food else "no food"}</div>
            </div>"""
        else:
            slots_html += f"""
            <div style="background:#F4F7FB;border-radius:10px;padding:10px 6px;text-align:center;">
              <div style="font-size:18px;opacity:0.3;">{icon}</div>
              <div style="font-size:9px;color:#C0C8D0;margin-top:3px;">{slot.capitalize()}</div>
              <div style="font-size:13px;color:#C0C8D0;margin-top:3px;">—</div>
            </div>"""
    slots_html += "</div>"
    html += section("⏰ When to Take", slots_html)

    if drug_info.side_effects:
        se_html = ""
        for se in drug_info.side_effects[:6]:
            bg  = severity_color.get(se.severity, "#F4F7FB")
            tc  = severity_text.get(se.severity, "#0D1B2A")
            dot = severity_dot.get(se.severity, "#888")
            tag = severity_tag.get(se.severity, "Monitor")
            se_html += f"""
            <div style="display:flex;align-items:flex-start;gap:8px;padding:9px 10px;
                        border-radius:9px;background:{bg};margin-bottom:6px;">
              <div style="width:8px;height:8px;border-radius:50%;background:{dot};
                          flex-shrink:0;margin-top:3px;"></div>
              <div style="flex:1;">
                <div style="font-size:12px;font-weight:600;color:{tc};">{se.name}</div>
                <div style="font-size:11px;color:{tc};opacity:0.85;margin-top:1px;">
                  {se.description}</div>
              </div>
              <div style="font-size:9px;padding:2px 7px;border-radius:5px;
                          background:rgba(255,255,255,0.6);color:{tc};
                          font-weight:600;white-space:nowrap;">{tag}</div>
            </div>"""
        html += section("⚡ Side Effects", se_html)

    if drug_info.food_interactions:
        fi_html = '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
        for fi in drug_info.food_interactions:
            bg   = food_color.get(fi.action, "#F4F7FB")
            tc   = food_text.get(fi.action, "#0D1B2A")
            icon = food_icon.get(fi.action, "")
            fi_html += f"""
            <div style="display:flex;align-items:center;gap:5px;padding:7px 11px;
                        border-radius:20px;background:{bg};font-size:12px;
                        font-weight:500;color:{tc};" title="{fi.reason}">
              {icon} {fi.substance}</div>"""
        fi_html += "</div>"
        html += section("🍽 Food & Drink", fi_html)

    if drug_info.warnings:
        w_html = ""
        for w in drug_info.warnings[:5]:
            w_html += f"""
            <div style="font-size:12px;color:#78350F;padding:5px 0;
                        border-bottom:1px solid #FDE68A;line-height:1.5;">· {w.text}</div>"""
        html += f"""
        <div style="background:#FFFBEB;border:1px solid #FCD34D;border-radius:14px;
                    padding:16px;margin-bottom:12px;">
          <div style="font-size:10px;font-weight:700;color:#92400E;text-transform:uppercase;
                      letter-spacing:0.1em;margin-bottom:10px;">⚠️ Warnings</div>
          {w_html}</div>"""

    if drug_info.emergency_signs:
        e_html = ""
        for e in drug_info.emergency_signs[:4]:
            e_html += f'<div style="font-size:12px;color:#7F1D1D;padding:4px 0;">· {e}</div>'
        html += f"""
        <div style="background:#FEF2F2;border:1px solid #FCA5A5;border-radius:14px;
                    padding:16px;margin-bottom:12px;">
          <div style="font-size:10px;font-weight:700;color:#991B1B;text-transform:uppercase;
                      letter-spacing:0.1em;margin-bottom:10px;">🚨 Seek Help Immediately If:</div>
          {e_html}</div>"""

    html += """
      <div style="text-align:center;padding-top:8px;">
        <div style="font-size:10px;color:#9BA8B5;line-height:1.6;">
          Powered by Gemma 4 · Verified against NIH DailyMed<br>
          For reference only · Always consult your doctor or pharmacist
        </div>
      </div>
    </div>"""
    return html


def scan_image(pil_image, model, tokenizer):
    """Step 1: scan image and return detected drug name only."""
    if pil_image is None:
        return "", "<div style='color:#991B1B;padding:1rem;'>No image provided.</div>"
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer)
        if drug_name:
            return drug_name, f"""
            <div style='background:#F0FDF4;border:1px solid #6EE7B7;border-radius:10px;
                        padding:12px 16px;font-size:13px;color:#065F46;'>
              ✅ Detected: <strong>{drug_name}</strong>
              <span style='font-size:11px;color:#6B7B8D;margin-left:8px;'>(via {method})</span><br>
              <span style='font-size:12px;color:#6B7B8D;margin-top:4px;display:block;'>
                Check the name above — edit if needed, then click Generate.</span>
            </div>"""
        else:
            return "", """
            <div style='background:#FEF3C7;border:1px solid #FCD34D;border-radius:10px;
                        padding:12px 16px;font-size:13px;color:#92400E;'>
              ⚠️ Could not detect drug name from image.<br>
              <span style='font-size:12px;'>Please type the drug name in the field below.</span>
            </div>"""
    except Exception as e:
        return "", f"<div style='color:#991B1B;padding:1rem;'>Scan error: {str(e)}</div>"


def generate_guide(drug_name, age_group, pregnant,
                   kidney_issue, liver_issue, other_meds, model, tokenizer):
    """Step 2: generate guide from drug name."""
    from extract import extract_drug_info_robust
    try:
        if not drug_name.strip():
            return "<div style='color:#991B1B;padding:1rem;'>Please enter a drug name first.</div>"

        leaflet_text = get_drug_leaflet(drug_name.strip())
        if not leaflet_text:
            return (f"<div style='padding:1rem;color:#92400E;background:#FEF3C7;"
                    f"border-radius:10px;'>'{drug_name}' not found in DailyMed. "
                    f"Check spelling or try the generic name.</div>")

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
        return f"<div style='color:#991B1B;padding:1rem;'>Error: {str(e)}</div>"


def build_demo(model, tokenizer):

    tess_ok, tess_msg = tesseract_status()
    tess_badge = (
        f"<span style='color:#065F46;background:#D1FAE5;padding:3px 9px;"
        f"border-radius:5px;font-size:11px;'>✅ {tess_msg}</span>"
        if tess_ok else
        f"<span style='color:#991B1B;background:#FEE2E2;padding:3px 9px;"
        f"border-radius:5px;font-size:11px;'>⚠️ {tess_msg}</span>"
    )

    def _scan(pil_image):
        return scan_image(pil_image, model, tokenizer)

    def _generate(drug_name, age_group, pregnant, kidney_issue, liver_issue, other_meds):
        return generate_guide(drug_name, age_group, pregnant,
                              kidney_issue, liver_issue, other_meds, model, tokenizer)

    with gr.Blocks(
        title="Legimed",
        theme=gr.themes.Soft(),
        css="""
        .gradio-container { max-width: 480px !important; margin: 0 auto !important; }
        footer { display: none !important; }
        """
    ) as demo:

        gr.HTML("""
        <div style="text-align:center;padding:20px 0 8px;">
          <div style="font-size:26px;font-weight:700;color:#0D1B2A;">💊 Legimed</div>
          <div style="font-size:13px;color:#6B7B8D;margin-top:4px;">
            Your medication, made legible</div>
        </div>""")

        # Step 1: Image scan
        gr.HTML("<div style='font-size:13px;font-weight:600;color:#0D1B2A;margin:8px 0 6px;'>Step 1 · Scan or type drug name</div>")
        with gr.Group():
            image_input = gr.Image(
                type="pil",
                label="📷 Scan drug box (optional)",
                sources=["upload", "webcam", "clipboard"],
                height=200,
            )
            gr.HTML(value=tess_badge)
            scan_btn = gr.Button("🔍 Scan image", variant="secondary", size="sm")
            scan_status = gr.HTML(value="")
            drug_input = gr.Textbox(
                label="💊 Drug name",
                placeholder="Auto-filled after scan, or type here",
            )

        # Step 2: Profile
        gr.HTML("<div style='font-size:13px;font-weight:600;color:#0D1B2A;margin:12px 0 6px;'>Step 2 · Your profile</div>")
        with gr.Group():
            age_input  = gr.Radio(choices=["adult", "elderly"], value="adult", label="Age group")
            preg_input = gr.Checkbox(label="Pregnant or breastfeeding")
            kid_input  = gr.Checkbox(label="Kidney condition")
            liv_input  = gr.Checkbox(label="Liver condition")
            meds_input = gr.Textbox(label="Other medications", placeholder="e.g. aspirin, metformin")

        # Step 3: Generate
        gr.HTML("<div style='font-size:13px;font-weight:600;color:#0D1B2A;margin:12px 0 6px;'>Step 3 · Generate</div>")
        generate_btn = gr.Button("Generate my guide →", variant="primary", size="lg")

        gr.HTML("<div style='font-size:13px;font-weight:600;color:#0D1B2A;margin:12px 0 6px;'>Your guide</div>")
        output = gr.HTML(
            value="<div style='color:#9BA8B5;font-size:13px;padding:1rem;text-align:center;'>"
                  "Complete steps above to generate your guide.</div>"
        )

        # Scan button: just identify drug name
        scan_btn.click(
            fn=lambda: (gr.update(interactive=False), ""),
            inputs=None,
            outputs=[scan_btn, scan_status],
            queue=False
        ).then(
            fn=_scan,
            inputs=[image_input],
            outputs=[drug_input, scan_status]
        ).then(
            fn=lambda: gr.update(interactive=True),
            inputs=None,
            outputs=[scan_btn],
            queue=False
        )

        # Generate button: produce full guide
        generate_btn.click(
            fn=lambda: "<div style='color:#1D9E75;font-size:13px;padding:1rem;text-align:center;'>"
                       "⏳ Generating your guide… (~45 seconds)</div>",
            inputs=None,
            outputs=output,
            queue=False
        ).then(
            fn=_generate,
            inputs=[drug_input, age_input, preg_input, kid_input, liv_input, meds_input],
            outputs=output
        )

        gr.HTML("""
        <div style="text-align:center;padding:16px 0 8px;">
          <div style="font-size:10px;color:#9BA8B5;">
            Gemma 4 · NIH DailyMed · Apache 2.0 ·
            <a href="https://github.com/LorraineWong/legimed" style="color:#1D9E75;">GitHub</a>
          </div>
        </div>""")

    return demo
