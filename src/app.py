import gradio as gr
from dailymed import get_drug_leaflet
from personalise import personalise, generate_personal_summary
from schema import UserProfile
from vision import image_to_drug_name


def format_html_output(drug_info, personal_summary) -> str:
    severity_border = {"HIGH": "#E53E3E", "MEDIUM": "#F6AD55", "LOW": "#38A169"}
    severity_tag_bg = {"HIGH": "#FEE2E2", "MEDIUM": "#FFF7E6", "LOW": "#E6FFFA"}
    severity_text = {"HIGH": "#9B2C2C", "MEDIUM": "#B7791F", "LOW": "#2F855A"}
    severity_tag = {"HIGH": "Emergency", "MEDIUM": "Call doctor", "LOW": "Monitor"}
    food_color = {"avoid": "#FEE2E2", "caution": "#FFF7E6", "ok": "#E6FFFA"}
    food_text = {"avoid": "#9B2C2C", "caution": "#B7791F", "ok": "#2F855A"}
    food_icon = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    def section(label, content):
        return f"""
        <div style="background:#fff;border-radius:18px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);
                    padding:18px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;color:#00A878;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:12px;">{label}</div>
          {content}
        </div>"""

    html = f"""
    <div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;
                background:#F7FAFC;padding:16px;border-radius:20px;max-width:600px;margin:0 auto;">
      <div style="background:linear-gradient(135deg,#00A878,#00875F);border-radius:18px;
                  box-shadow:0 2px 8px rgba(0,0,0,0.08);
                  padding:20px;margin-bottom:12px;color:#fff;">
        <div style="font-size:25px;font-weight:800;line-height:1.2;">{drug_info.drug_name}</div>
        <div style="font-size:13px;opacity:0.95;margin-top:6px;">
          Active ingredient: {drug_info.active_ingredient}
        </div>
        <div style="display:inline-block;margin-top:10px;background:rgba(255,255,255,0.22);
                    border:1px solid rgba(255,255,255,0.35);padding:6px 10px;border-radius:999px;
                    font-size:11px;font-weight:600;">
          Class: {drug_info.drug_class}
        </div>
      </div>"""

    if personal_summary:
        html += section("📋 Your Summary", f"""
          <div style="font-size:14px;color:#1f2937;line-height:1.7;
                      background:#F0FFF8;border-radius:12px;padding:14px;
                      border-left:4px solid #00A878;">{personal_summary}</div>""")

    time_slots = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "bedtime": "🌙"}
    dose_map = {d.time_of_day: d for d in drug_info.dosage_instructions}
    slots_html = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;">'
    for slot, icon in time_slots.items():
        d = dose_map.get(slot)
        if d:
            slots_html += f"""
            <div style="background:#E6FFFA;border:1px solid #8FDCC5;border-radius:12px;
                        padding:10px 6px;text-align:center;">
              <div style="font-size:18px;">{icon}</div>
              <div style="font-size:9px;color:#4A5568;margin-top:3px;">{slot.capitalize()}</div>
              <div style="font-size:12px;font-weight:800;color:#065F46;margin-top:3px;">
                {d.amount if d.amount else "—"}</div>
              <div style="font-size:9px;color:#4A5568;">
                {"with food" if d.with_food else "no food"}</div>
            </div>"""
        else:
            slots_html += f"""
            <div style="background:#EDF2F7;border-radius:12px;padding:10px 6px;text-align:center;">
              <div style="font-size:18px;opacity:0.3;">{icon}</div>
              <div style="font-size:9px;color:#A0AEC0;margin-top:3px;">{slot.capitalize()}</div>
              <div style="font-size:13px;color:#A0AEC0;margin-top:3px;">—</div>
            </div>"""
    slots_html += "</div>"
    html += section("⏰ When to Take", slots_html)

    if drug_info.side_effects:
        se_html = ""
        for se in drug_info.side_effects[:6]:
            border = severity_border.get(se.severity, "#CBD5E0")
            tc = severity_text.get(se.severity, "#2D3748")
            tag = severity_tag.get(se.severity, "Monitor")
            tag_bg = severity_tag_bg.get(se.severity, "#EDF2F7")
            se_html += f"""
            <div style="display:flex;align-items:flex-start;gap:10px;padding:10px 12px;
                        border-radius:12px;border-left:4px solid {border};
                        background:#fff;margin-bottom:8px;box-shadow:0 1px 3px rgba(0,0,0,0.06);">
              <div style="flex:1;">
                <div style="font-size:13px;font-weight:700;color:#1A202C;line-height:1.4;">{se.name}</div>
                <div style="font-size:12px;color:{tc};line-height:1.5;margin-top:2px;">
                  {se.description}</div>
              </div>
              <div style="font-size:10px;padding:4px 8px;border-radius:999px;
                          background:{tag_bg};color:{tc};
                          font-weight:700;white-space:nowrap;">{tag}</div>
            </div>"""
        html += section("⚡ Side Effects", se_html)

    if drug_info.food_interactions:
        fi_html = '<div style="display:flex;gap:8px;flex-wrap:wrap;">'
        for fi in drug_info.food_interactions:
            bg = food_color.get(fi.action, "#F4F7FB")
            tc = food_text.get(fi.action, "#0D1B2A")
            icon = food_icon.get(fi.action, "")
            fi_html += f"""
            <div style="display:flex;align-items:center;gap:5px;padding:7px 11px;
                        border-radius:999px;background:{bg};font-size:12px;
                        font-weight:600;color:{tc};" title="{fi.reason}">
              {icon} {fi.substance}</div>"""
        fi_html += "</div>"
        html += section("🍽 Food & Drink", fi_html)
    else:
        html += section(
            "🍽 Food & Drink",
            "<div style='font-size:13px;color:#718096;'>No specific food interactions found</div>"
        )

    if drug_info.warnings:
        w_html = ""
        for w in drug_info.warnings[:5]:
            w_html += f"""
            <div style="font-size:12px;color:#744210;padding:4px 0;line-height:1.6;">• {w.text}</div>"""
        html += f"""
        <div style="background:#FFFBF0;border-left:4px solid #F6AD55;border-radius:18px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);
                    padding:18px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:700;color:#B7791F;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:10px;">⚠️ Warnings</div>
          {w_html}</div>"""

    if drug_info.emergency_signs:
        e_html = ""
        for e in drug_info.emergency_signs[:4]:
            e_html += f'<div style="font-size:12px;color:#7F1D1D;padding:4px 0;line-height:1.6;">• {e}</div>'
        html += f"""
        <div style="background:#FFF5F5;border:1px solid #FEB2B2;border-radius:18px;
                    box-shadow:0 2px 8px rgba(0,0,0,0.08);
                    padding:18px;margin-bottom:12px;">
          <div style="font-size:11px;font-weight:800;color:#C53030;text-transform:uppercase;
                      letter-spacing:0.08em;margin-bottom:10px;">🚨 Seek Help Immediately If:</div>
          {e_html}</div>"""

    html += """
      <div style="text-align:center;padding-top:8px;">
        <div style="font-size:10px;color:#718096;line-height:1.7;">
          Powered by Gemma 4 · Verified against NIH DailyMed<br>
          For reference only · Always consult your doctor or pharmacist
        </div>
      </div>
    </div>"""
    return html


def scan_image(pil_image, model, tokenizer, processor=None):
    """Step 1: scan image and return detected drug name only."""
    if pil_image is None:
        return "", "<div style='color:#991B1B;padding:1rem;'>No image provided.</div>"
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer, processor)
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
            processor_hint = ""
            if model is not None and tokenizer is not None and processor is None:
                processor_hint = "Gemma vision processor not loaded; "
            return "", f"""
            <div style='background:#FEF3C7;border:1px solid #FCD34D;border-radius:10px;
                        padding:12px 16px;font-size:13px;color:#92400E;'>
              ⚠️ Could not detect drug name from image.<br>
              <span style='font-size:12px;'>{processor_hint}please type the drug name in the field below.</span>
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


def build_demo(model, tokenizer, processor=None):
    tess_ok, tess_msg = tesseract_status()
    tess_badge = (
        f"<span style='color:#065F46;background:#D1FAE5;padding:3px 9px;"
        f"border-radius:5px;font-size:11px;'>✅ {tess_msg}</span>"
        if tess_ok else
        f"<span style='color:#991B1B;background:#FEE2E2;padding:3px 9px;"
        f"border-radius:5px;font-size:11px;'>⚠️ {tess_msg}</span>"
    )

    def _scan(pil_image):
        return scan_image(pil_image, model, tokenizer, processor)

    def _generate(drug_name, age_group, pregnant, kidney_issue, liver_issue, other_meds):
        return generate_guide(drug_name, age_group, pregnant,
                              kidney_issue, liver_issue, other_meds, model, tokenizer)

    with gr.Blocks(
        title="Legimed",
        theme=gr.themes.Base(),
        css="""
        .gradio-container {
            max-width: 500px !important;
            margin: 0 auto !important;
            background: #F7F8FA !important;
            padding: 0 12px 40px !important;
        }
        footer { display: none !important; }
        .legimed-step {
            display:flex; align-items:center; gap:10px; margin: 10px 0 8px; color:#1A202C;
            font-size:13px; font-weight:700;
        }
        .legimed-step .num {
            width:24px; height:24px; border-radius:999px; background:#00A878; color:#fff;
            display:flex; align-items:center; justify-content:center; font-size:12px; font-weight:800;
            box-shadow:0 2px 6px rgba(0,168,120,0.3);
        }
        .scan-zone { border:2px dashed #B2F5EA; border-radius:18px; padding:10px; background:#F8FFFD; }
        .scan-or-type { text-align:center; color:#718096; font-size:11px; margin:8px 0; }
        .gradio-container .legimed-primary button {
            width:100%; border-radius:999px !important; border:none !important;
            background:linear-gradient(135deg,#00A878,#00875F) !important;
            font-weight:800 !important; font-size:15px !important; padding:14px 16px !important;
        }
        .gradio-container .toggle-card { border:1px solid #E2E8F0; border-radius:14px; padding:8px 10px; }
        .gradio-container .wrap .gr-radio { gap:8px; }
        .gradio-container .wrap .gr-radio label {
            border:1px solid #B2F5EA !important; border-radius:999px !important;
            background:#F8FFFD !important; padding:8px 14px !important;
        }
        .gradio-container .wrap .gr-radio label:has(input:checked) {
            background:#E6FFFA !important; border-color:#00A878 !important;
            color:#065F46 !important; font-weight:700 !important;
        }
        """
    ) as demo:

        gr.HTML("""
        <div style="text-align:center;padding:20px 0 10px;">
          <div style="font-size:38px;line-height:1;">💊</div>
          <div style="font-size:30px;font-weight:800;color:#1A202C;line-height:1.1;margin-top:2px;">Legimed</div>
          <div style="font-size:13px;color:#718096;margin-top:6px;line-height:1.5;">
            Your medication, made legible</div>
        </div>""")

        # Step 1: Image scan
        gr.HTML("<div class='legimed-step'><span class='num'>1</span><span>Scan medicine box or type drug name</span></div>")
        with gr.Group():
            gr.HTML("<div style='font-size:12px;color:#718096;margin-bottom:6px;'>📷 Upload a medicine photo for automatic detection</div>")
            image_input = gr.Image(
                type="pil",
                label="Camera / Upload",
                sources=["upload", "webcam", "clipboard"],
                height=200,
                elem_classes=["scan-zone"]
            )
            scan_btn = gr.Button("🔍 Scan image", variant="secondary", size="sm")
            scan_status = gr.HTML(value="")
            gr.HTML("<div class='scan-or-type'>— or type below —</div>")
            drug_input = gr.Textbox(
                label="🔎 Drug name",
                placeholder="Auto-filled after scan, or type here",
                scale=1
            )

        # Step 2: Profile
        gr.HTML("<div class='legimed-step'><span class='num'>2</span><span>Your health profile</span></div>")
        with gr.Group():
            age_input  = gr.Radio(choices=["adult", "elderly"], value="adult", label="👤 Age group", info="Select one")
            preg_input = gr.Checkbox(label="🤰 Pregnant or breastfeeding", elem_classes=["toggle-card"])
            kid_input  = gr.Checkbox(label="🫘 Kidney condition", elem_classes=["toggle-card"])
            liv_input  = gr.Checkbox(label="🫀 Liver condition", elem_classes=["toggle-card"])
            meds_input = gr.Textbox(label="💊 Other medications", placeholder="e.g. aspirin, metformin")

        # Step 3: Generate
        gr.HTML("<div class='legimed-step'><span class='num'>3</span><span>Generate your personalised guide</span></div>")
        generate_btn = gr.Button("Generate my guide →", variant="primary", size="lg", elem_classes=["legimed-primary"])

        gr.HTML("<div style='font-size:13px;font-weight:700;color:#1A202C;margin:12px 0 6px;'>Your guide</div>")
        output = gr.HTML(
            value="<div style='color:#718096;font-size:13px;padding:1rem;text-align:center;'>"
                  "Complete steps above to generate your guide.</div>"
        )

        gr.HTML("""
        <div style="text-align:center;padding:20px 0 8px;">
          <div style="font-size:11px;color:#A0AEC0;line-height:1.6;">
            Powered by Gemma 4 · NIH DailyMed · Apache 2.0<br>
            <a href="https://github.com/LorraineWong/legimed"
               style="color:#00A878;text-decoration:none;">GitHub</a>
          </div>
        </div>""")

        # ── Events ───────────────────────────────────────
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

        generate_btn.click(
            fn=lambda: """
            <div style='text-align:center;padding:40px 20px;color:#00A878;font-size:13px;
                        background:white;border-radius:16px;'>
              ⏳ Generating your personalised guide…<br>
              <span style='font-size:12px;color:#718096;'>This takes about 45 seconds</span>
            </div>""",
            inputs=None,
            outputs=output,
            queue=False
        ).then(
            fn=_generate,
            inputs=[drug_input, age_input, sex_input, preg_input, bf_input,
                    kidney_input, liver_input, heart_input, db_input,
                    bp_input, asthma_input, other_cond_input, meds_input],
            outputs=output
        )

    return demo

