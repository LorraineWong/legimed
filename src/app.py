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


def _status_html(type_, msg):
    styles = {
        "success": ("background:#F0FDF4;border:1px solid #6EE7B7;color:#065F46;", "✅"),
        "warning": ("background:#FEF3C7;border:1px solid #FCD34D;color:#92400E;", "⚠️"),
        "error":   ("background:#FEF2F2;border:1px solid #FEB2B2;color:#9B2C2C;", "❌"),
    }
    style, icon = styles.get(type_, styles["error"])
    return (f"<div style='{style}border-radius:10px;padding:10px 14px;"
            f"font-size:13px;margin-top:6px;'>{icon} {msg}</div>")


def format_html_output(drug_info, personal_summary) -> str:
    severity_border = {"HIGH": "#E53E3E", "MEDIUM": "#F6AD55", "LOW": "#38A169"}
    severity_tag_bg = {"HIGH": "#FEE2E2", "MEDIUM": "#FFF7E6", "LOW": "#E6FFFA"}
    severity_text   = {"HIGH": "#9B2C2C", "MEDIUM": "#B7791F", "LOW": "#276749"}
    severity_tag    = {"HIGH": "🚨 Emergency", "MEDIUM": "📞 Call doctor", "LOW": "👁 Monitor"}
    food_color = {"avoid": "#FEE2E2", "caution": "#FFF7E6", "ok": "#E6FFFA"}
    food_text  = {"avoid": "#9B2C2C", "caution": "#B7791F", "ok": "#276749"}
    food_icon  = {"avoid": "🚫", "caution": "⚠️", "ok": "✅"}

    def card(content, extra=""):
        return (f'<div style="background:#ffffff;border-radius:14px;'
                f'box-shadow:0 1px 6px rgba(0,0,0,0.07);padding:14px 16px;'
                f'margin-bottom:10px;{extra}">{content}</div>')

    def slabel(t):
        return (f'<div style="font-size:10px;font-weight:700;color:#00A878;'
                f'text-transform:uppercase;letter-spacing:0.08em;'
                f'margin-bottom:10px;">{t}</div>')

    html = ('<div style="font-family:-apple-system,BlinkMacSystemFont,'
            "'Segoe UI',sans-serif;background:#F7FAFC;padding:14px;"
            'border-radius:16px;max-width:520px;margin:0 auto;color:#1A202C;">')

    html += (f'<div style="background:linear-gradient(135deg,#00A878,#00875F);'
             f'border-radius:14px;padding:18px;margin-bottom:10px;color:#ffffff;">'
             f'<div style="font-size:21px;font-weight:800;color:#ffffff;">'
             f'{drug_info.drug_name}</div>'
             f'<div style="font-size:12px;opacity:0.9;margin-top:4px;color:#ffffff;">'
             f'{drug_info.active_ingredient}</div>'
             f'<div style="display:inline-block;margin-top:8px;'
             f'background:rgba(255,255,255,0.2);border:1px solid rgba(255,255,255,0.3);'
             f'padding:3px 10px;border-radius:999px;font-size:11px;'
             f'font-weight:600;color:#ffffff;">{drug_info.drug_class}</div></div>')

    if personal_summary:
        html += card(
            slabel("📋 Your Summary") +
            f'<div style="font-size:13px;color:#1A202C;line-height:1.7;'
            f'background:#F0FFF8;border-radius:10px;padding:12px;'
            f'border-left:3px solid #00A878;">{personal_summary}</div>'
        )

    time_slots = {"morning": "🌅", "afternoon": "☀️", "evening": "🌆", "bedtime": "🌙"}
    dose_map = {d.time_of_day: d for d in drug_info.dosage_instructions}
    slots = '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;">'
    for slot, icon in time_slots.items():
        d = dose_map.get(slot)
        if d:
            slots += (f'<div style="background:#E6FFFA;border:1px solid #8FDCC5;'
                      f'border-radius:10px;padding:8px 4px;text-align:center;">'
                      f'<div style="font-size:16px;">{icon}</div>'
                      f'<div style="font-size:9px;color:#4A5568;margin-top:2px;">'
                      f'{slot.capitalize()}</div>'
                      f'<div style="font-size:11px;font-weight:800;color:#065F46;'
                      f'margin-top:2px;">{d.amount if d.amount else "—"}</div>'
                      f'<div style="font-size:9px;color:#4A5568;">'
                      f'{"with food" if d.with_food else "no food"}</div></div>')
        else:
            slots += (f'<div style="background:#EDF2F7;border-radius:10px;'
                      f'padding:8px 4px;text-align:center;">'
                      f'<div style="font-size:16px;opacity:0.2;">{icon}</div>'
                      f'<div style="font-size:9px;color:#A0AEC0;margin-top:2px;">'
                      f'{slot.capitalize()}</div>'
                      f'<div style="font-size:12px;color:#A0AEC0;margin-top:2px;">—</div>'
                      f'</div>')
    slots += "</div>"
    html += card(slabel("⏰ When to Take") + slots)

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
            se_html += (f'<div style="display:flex;align-items:flex-start;gap:8px;'
                        f'padding:9px 10px;border-radius:10px;'
                        f'border-left:3px solid {border};'
                        f'background:#FAFAFA;margin-bottom:6px;">'
                        f'<div style="flex:1;">'
                        f'<div style="font-size:12px;font-weight:700;color:#1A202C;">'
                        f'{se.name}</div>'
                        f'<div style="font-size:11px;color:{tc};line-height:1.5;'
                        f'margin-top:1px;">{se.description}</div></div>'
                        f'<div style="font-size:9px;padding:3px 7px;border-radius:999px;'
                        f'background:{tag_bg};color:{tc};font-weight:700;'
                        f'white-space:nowrap;flex-shrink:0;">{tag}</div></div>')
        html += card(slabel("⚡ Side Effects") + se_html)

    food_items = [fi for fi in drug_info.food_interactions if _is_food(fi.substance)]
    if food_items:
        fi_html = '<div style="display:flex;gap:6px;flex-wrap:wrap;">'
        for fi in food_items:
            bg   = food_color.get(fi.action, "#F4F7FB")
            tc   = food_text.get(fi.action, "#1A202C")
            icon = food_icon.get(fi.action, "")
            fi_html += (f'<div style="display:flex;align-items:center;gap:4px;'
                        f'padding:6px 10px;border-radius:999px;background:{bg};'
                        f'font-size:12px;font-weight:600;color:{tc};"'
                        f' title="{fi.reason}">{icon} {fi.substance}</div>')
        fi_html += "</div>"
        html += card(slabel("🍽 Food & Drink") + fi_html)
    else:
        html += card(slabel("🍽 Food & Drink") +
                     '<div style="font-size:12px;color:#718096;">'
                     'No specific food interactions found.</div>')

    if drug_info.warnings:
        w_html = ""
        for w in drug_info.warnings[:3]:
            text = w.text
            if len(text) > 100:
                text = text[:100].rsplit(" ", 1)[0].rstrip(".,;") + "…"
            w_html += (f'<div style="font-size:12px;color:#744210;padding:4px 0;'
                       f'border-bottom:1px solid #FDE68A;line-height:1.6;">• {text}</div>')
        html += (f'<div style="background:#FFFBF0;border-left:3px solid #F6AD55;'
                 f'border-radius:14px;box-shadow:0 1px 6px rgba(0,0,0,0.06);'
                 f'padding:14px 16px;margin-bottom:10px;">'
                 f'<div style="font-size:10px;font-weight:700;color:#B7791F;'
                 f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
                 f'⚠️ Warnings</div>{w_html}</div>')

    if drug_info.emergency_signs:
        e_html = ""
        for e in drug_info.emergency_signs[:3]:
            e_html += (f'<div style="font-size:12px;color:#7F1D1D;'
                       f'padding:3px 0;line-height:1.6;">• {e}</div>')
        html += (f'<div style="background:#FFF5F5;border:1px solid #FEB2B2;'
                 f'border-radius:14px;box-shadow:0 1px 6px rgba(0,0,0,0.06);'
                 f'padding:14px 16px;margin-bottom:10px;">'
                 f'<div style="font-size:10px;font-weight:800;color:#C53030;'
                 f'text-transform:uppercase;letter-spacing:0.08em;margin-bottom:8px;">'
                 f'🚨 Seek Help Immediately If:</div>{e_html}</div>')

    html += ('<div style="text-align:center;padding-top:6px;">'
             '<div style="font-size:10px;color:#A0AEC0;line-height:1.7;">'
             'Powered by Gemma 4 · NIH DailyMed<br>'
             'For reference only · Always consult your doctor or pharmacist'
             '</div></div></div>')
    return html


def scan_image(pil_image, model, tokenizer, processor=None):
    if pil_image is None:
        return "", _status_html("error", "No image provided.")
    try:
        drug_name, method = image_to_drug_name(pil_image, model, tokenizer, processor)
        if drug_name:
            return drug_name, _status_html(
                "success",
                f"Detected: <strong>{drug_name}</strong> "
                f"<span style='font-size:11px;color:#718096;'>(via {method})</span><br>"
                f"<span style='font-size:11px;'>Edit if needed, then click Generate.</span>")
        else:
            return "", _status_html("warning",
                "Could not detect drug name. Please type it below.")
    except Exception as e:
        return "", _status_html("error", f"Scan error: {str(e)}")


def generate_guide(drug_name, profile_json, model, tokenizer):
    import json
    from extract import extract_drug_info_robust
    try:
        if not drug_name.strip():
            return _status_html("error", "Please enter a drug name first.")
        p = json.loads(profile_json)
        leaflet_text = get_drug_leaflet(drug_name.strip())
        if not leaflet_text:
            return _status_html("warning",
                f"'{drug_name}' not found in DailyMed. "
                f"Try the generic name (e.g. paracetamol instead of Panadol).")
        profile = UserProfile(
            age_group=p.get("age_group", "adult"),
            sex=p.get("sex", "prefer_not_to_say"),
            pregnant=p.get("pregnant", False) and p.get("sex") == "female",
            breastfeeding=p.get("breastfeeding", False) and p.get("sex") == "female",
            heart_condition=p.get("heart_condition", False),
            diabetes=p.get("diabetes", False),
            hypertension=p.get("hypertension", False),
            asthma=p.get("asthma", False),
            kidney_issue=p.get("kidney_issue", False),
            liver_issue=p.get("liver_issue", False),
            allergies=[a.strip() for a in p.get("allergies", "").split(",") if a.strip()],
            other_medications=[m.strip() for m in p.get("other_meds", "").split(",") if m.strip()]
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

    def _generate(drug_name, profile_json):
        return generate_guide(drug_name, profile_json, model, tokenizer)

    CSS = """
    * { box-sizing: border-box; }
    body, .gradio-container, .main, .wrap, .app, .svelte-1gfkn6j {
        background: #F7F8FA !important;
        color: #1A202C !important;
    }
    .gradio-container {
        max-width: 520px !important;
        min-width: 320px !important;
        margin: 0 auto !important;
        padding: 0 0 40px !important;
        overflow-x: hidden !important;
    }
    footer { display: none !important; }
    """

    FORM_HTML = """
<div id="legimed-app" style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
     background:#F7F8FA;max-width:520px;margin:0 auto;padding:0 12px 16px;color:#1A202C;">

  <!-- Header -->
  <div style="text-align:center;padding:20px 0 8px;">
    <div style="font-size:34px;">💊</div>
    <div style="font-size:26px;font-weight:800;color:#1A202C;margin-top:2px;">Legimed</div>
    <div style="font-size:13px;color:#718096;margin-top:4px;">Your medication, made legible</div>
  </div>

  <!-- Step 1 -->
  <div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px;">
    <div style="width:22px;height:22px;border-radius:50%;background:#00A878;color:#fff;
         font-size:11px;font-weight:800;display:flex;align-items:center;
         justify-content:center;">1</div>
    <div style="font-size:13px;font-weight:700;color:#1A202C;">Your health profile</div>
  </div>

  <div style="background:#ffffff;border-radius:14px;border:1px solid #E2E8F0;padding:14px 16px;">

    <!-- Age group -->
    <div style="font-size:11px;font-weight:600;color:#718096;margin-bottom:6px;">Age group</div>
    <div style="display:flex;gap:6px;margin-bottom:12px;">
      <button onclick="setAge('child')" id="age-child"
        style="flex:1;padding:8px;border-radius:999px;border:1.5px solid #E2E8F0;
               background:#fff;color:#4A5568;font-size:12px;font-weight:600;cursor:pointer;">
        Child</button>
      <button onclick="setAge('adult')" id="age-adult"
        style="flex:1;padding:8px;border-radius:999px;border:1.5px solid #00A878;
               background:#E6FFFA;color:#065F46;font-size:12px;font-weight:700;cursor:pointer;">
        Adult</button>
      <button onclick="setAge('elderly')" id="age-elderly"
        style="flex:1;padding:8px;border-radius:999px;border:1.5px solid #E2E8F0;
               background:#fff;color:#4A5568;font-size:12px;font-weight:600;cursor:pointer;">
        Elderly</button>
    </div>

    <!-- Sex -->
    <div style="font-size:11px;font-weight:600;color:#718096;margin-bottom:6px;">Sex</div>
    <div style="display:flex;gap:6px;margin-bottom:12px;">
      <button onclick="setSex('male')" id="sex-male"
        style="flex:1;padding:8px;border-radius:999px;border:1.5px solid #00A878;
               background:#E6FFFA;color:#065F46;font-size:12px;font-weight:700;cursor:pointer;">
        Male</button>
      <button onclick="setSex('female')" id="sex-female"
        style="flex:1;padding:8px;border-radius:999px;border:1.5px solid #E2E8F0;
               background:#fff;color:#4A5568;font-size:12px;font-weight:600;cursor:pointer;">
        Female</button>
    </div>

    <!-- Conditions -->
    <div style="font-size:11px;font-weight:600;color:#718096;margin-bottom:8px;">
      Chronic conditions</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:12px;">
      <button onclick="toggleCond(this,'heart_condition')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">❤️ Heart disease</button>
      <button onclick="toggleCond(this,'diabetes')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🩸 Diabetes</button>
      <button onclick="toggleCond(this,'hypertension')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">💉 Hypertension</button>
      <button onclick="toggleCond(this,'asthma')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🫁 Asthma</button>
      <button onclick="toggleCond(this,'kidney_issue')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🫘 Kidney</button>
      <button onclick="toggleCond(this,'liver_issue')"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🫀 Liver</button>
      <button onclick="toggleCond(this,'pregnant')" id="btn-pregnant"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🤰 Pregnant</button>
      <button onclick="toggleCond(this,'breastfeeding')" id="btn-breastfeeding"
        style="padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
               background:#fff;color:#1A202C;font-size:12px;font-weight:500;
               text-align:left;cursor:pointer;">🍼 Breastfeeding</button>
    </div>

    <!-- Allergies -->
    <div style="font-size:11px;font-weight:600;color:#718096;margin-bottom:4px;">
      ⚠️ Known allergies</div>
    <input id="input-allergies" type="text"
      placeholder="e.g. penicillin, sulfa, aspirin"
      style="width:100%;padding:9px 12px;border-radius:10px;
             border:1.5px solid #E2E8F0;background:#F7F8FA;
             color:#1A202C;font-size:13px;margin-bottom:10px;outline:none;"
      oninput="updateProfile()"/>

    <!-- Current meds -->
    <div style="font-size:11px;font-weight:600;color:#718096;margin-bottom:4px;">
      💊 Current medications</div>
    <input id="input-meds" type="text"
      placeholder="e.g. aspirin, metformin, lisinopril"
      style="width:100%;padding:9px 12px;border-radius:10px;
             border:1.5px solid #E2E8F0;background:#F7F8FA;
             color:#1A202C;font-size:13px;outline:none;"
      oninput="updateProfile()"/>
  </div>

  <!-- Step 2 label -->
  <div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px;">
    <div style="width:22px;height:22px;border-radius:50%;background:#00A878;color:#fff;
         font-size:11px;font-weight:800;display:flex;align-items:center;
         justify-content:center;">2</div>
    <div style="font-size:13px;font-weight:700;color:#1A202C;">Your medication</div>
  </div>
</div>

<script>
var profile = {
  age_group: "adult", sex: "male",
  heart_condition:false, diabetes:false, hypertension:false, asthma:false,
  kidney_issue:false, liver_issue:false, pregnant:false, breastfeeding:false,
  allergies:"", other_meds:""
};

function setAge(v) {
  profile.age_group = v;
  ["child","adult","elderly"].forEach(function(a) {
    var b = document.getElementById("age-"+a);
    if (!b) return;
    if (a === v) {
      b.style.background="#E6FFFA"; b.style.borderColor="#00A878";
      b.style.color="#065F46"; b.style.fontWeight="700";
    } else {
      b.style.background="#fff"; b.style.borderColor="#E2E8F0";
      b.style.color="#4A5568"; b.style.fontWeight="600";
    }
  });
  updateProfile();
}

function setSex(v) {
  profile.sex = v;
  ["male","female"].forEach(function(s) {
    var b = document.getElementById("sex-"+s);
    if (!b) return;
    if (s === v) {
      b.style.background="#E6FFFA"; b.style.borderColor="#00A878";
      b.style.color="#065F46"; b.style.fontWeight="700";
    } else {
      b.style.background="#fff"; b.style.borderColor="#E2E8F0";
      b.style.color="#4A5568"; b.style.fontWeight="600";
    }
  });
  var show = v === "female";
  var pb = document.getElementById("btn-pregnant");
  var bb = document.getElementById("btn-breastfeeding");
  if (pb) pb.style.opacity = show ? "1" : "0.3";
  if (bb) bb.style.opacity = show ? "1" : "0.3";
  updateProfile();
}

function toggleCond(btn, key) {
  profile[key] = !profile[key];
  if (profile[key]) {
    btn.style.background="#E6FFFA"; btn.style.borderColor="#00A878";
    btn.style.color="#065F46"; btn.style.fontWeight="700";
  } else {
    btn.style.background="#fff"; btn.style.borderColor="#E2E8F0";
    btn.style.color="#1A202C"; btn.style.fontWeight="500";
  }
  updateProfile();
}

function updateProfile() {
  var a = document.getElementById("input-allergies");
  var m = document.getElementById("input-meds");
  if (a) profile.allergies = a.value;
  if (m) profile.other_meds = m.value;
  var el = document.getElementById("profile-state");
  if (el) el.value = JSON.stringify(profile);
  // Trigger Gradio change event
  var event = new Event("input", {bubbles:true});
  if (el) el.dispatchEvent(event);
}

// Init
document.addEventListener("DOMContentLoaded", function() { updateProfile(); });
setTimeout(function() { updateProfile(); }, 500);
</script>
"""

    with gr.Blocks(title="Legimed", css=CSS) as demo:

        gr.HTML(FORM_HTML)

        # Hidden state for profile JSON
        profile_state = gr.Textbox(
            value='{"age_group":"adult","sex":"male"}',
            visible=False,
            elem_id="profile-state"
        )

        # Image + scan (Gradio handles file upload)
        with gr.Group():
            image_input = gr.Image(
                type="pil",
                label="📷 Scan medicine box (optional)",
                sources=["upload", "webcam", "clipboard"],
                height=180,
            )
            scan_btn    = gr.Button("🔍 Scan image", variant="secondary", size="sm")
            scan_status = gr.HTML(value="")
            drug_input  = gr.Textbox(
                label="💊 Drug name",
                placeholder="Auto-filled after scan, or type here",
            )

        gr.HTML("""
        <div style="display:flex;align-items:center;gap:8px;margin:14px 0 8px;
                    padding:0 12px;">
          <div style="width:22px;height:22px;border-radius:50%;background:#00A878;
               color:#fff;font-size:11px;font-weight:800;display:flex;
               align-items:center;justify-content:center;">3</div>
          <div style="font-size:13px;font-weight:700;color:#1A202C;">
            Generate your guide</div>
        </div>""")

        generate_btn = gr.Button(
            "Generate my guide →", variant="primary", size="lg")

        gr.HTML("<div style='font-size:13px;font-weight:700;color:#1A202C;"
                "margin:14px 12px 6px;'>Your guide</div>")

        output = gr.HTML(
            value="<div style='color:#718096;font-size:13px;padding:2rem 1rem;"
                  "text-align:center;background:#ffffff;border-radius:14px;"
                  "border:1.5px dashed #E2E8F0;margin:0 12px;'>"
                  "Complete the steps above to generate your guide.</div>")

        gr.HTML("""<div style="text-align:center;padding:16px 0 4px;">
          <div style="font-size:10px;color:#A0AEC0;line-height:1.6;">
            Gemma 4 · NIH DailyMed · Apache 2.0 ·
            <a href="https://github.com/LorraineWong/legimed"
               style="color:#00A878;text-decoration:none;">GitHub</a>
          </div></div>""")

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
                        "border-radius:14px;margin:0 12px;'>⏳ Generating…<br>"
                        "<span style='font-size:11px;color:#718096;'>"
                        "About 45 seconds</span></div>"),
            inputs=None, outputs=output, queue=False
        ).then(
            fn=_generate,
            inputs=[drug_input, profile_state],
            outputs=output
        )

    return demo
