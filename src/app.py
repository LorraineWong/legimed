import gradio as gr
import base64
from io import BytesIO
from PIL import Image
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


def process_image_b64(img_b64: str, model, tokenizer, processor):
    """Decode base64 image and run Gemma vision."""
    try:
        img_data = base64.b64decode(img_b64)
        pil_image = Image.open(BytesIO(img_data)).convert("RGB")
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
        p = json.loads(profile_json) if profile_json else {}
        leaflet_text = get_drug_leaflet(drug_name.strip())
        if not leaflet_text:
            return _status_html("warning",
                f"'{drug_name}' not found in DailyMed. "
                f"Try the generic name (e.g. paracetamol instead of Panadol).")
        sex = p.get("sex", "male")
        profile = UserProfile(
            age_group=p.get("age_group", "adult"),
            sex=sex,
            pregnant=p.get("pregnant", False) and sex == "female",
            breastfeeding=p.get("breastfeeding", False) and sex == "female",
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

    def _scan(img_b64, drug_name_current):
        if not img_b64:
            return drug_name_current, _status_html("warning", "No image uploaded.")
        name, status = process_image_b64(img_b64, model, tokenizer, processor)
        return name or drug_name_current, status

    def _generate(drug_name, profile_json):
        return generate_guide(drug_name, profile_json, model, tokenizer)

    CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body, .gradio-container, .main, .wrap, .app {
        background: #F7F8FA !important;
    }
    .gradio-container {
        max-width: 520px !important;
        min-width: 320px !important;
        margin: 0 auto !important;
        padding: 0 !important;
        overflow-x: hidden !important;
    }
    footer, .built-with { display: none !important; }
    """

    UI_HTML = """
<style>
  #lm { font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
        background:#F7F8FA;max-width:520px;margin:0 auto;
        padding:0 12px 32px;color:#1A202C; }
  .lm-card { background:#fff;border-radius:14px;border:1px solid #E2E8F0;
             padding:14px 16px;margin-bottom:12px; }
  .lm-step { display:flex;align-items:center;gap:8px;margin:16px 0 8px; }
  .lm-step-num { width:22px;height:22px;border-radius:50%;background:#00A878;
                 color:#fff;font-size:11px;font-weight:800;display:flex;
                 align-items:center;justify-content:center;flex-shrink:0; }
  .lm-step-label { font-size:13px;font-weight:700;color:#1A202C; }
  .lm-label { font-size:11px;font-weight:600;color:#718096;margin-bottom:6px; }
  .lm-pill-group { display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px; }
  .lm-pill { padding:8px 16px;border-radius:999px;border:1.5px solid #E2E8F0;
             background:#fff;color:#4A5568;font-size:12px;font-weight:600;
             cursor:pointer;transition:all 0.15s; }
  .lm-pill.active { background:#E6FFFA;border-color:#00A878;
                    color:#065F46;font-weight:700; }
  .lm-cond-grid { display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:12px; }
  .lm-cond { padding:9px 10px;border-radius:10px;border:1.5px solid #E2E8F0;
             background:#fff;color:#1A202C;font-size:12px;font-weight:500;
             text-align:left;cursor:pointer;transition:all 0.15s; }
  .lm-cond.active { background:#E6FFFA;border-color:#00A878;
                    color:#065F46;font-weight:700; }
  .lm-input { width:100%;padding:9px 12px;border-radius:10px;
              border:1.5px solid #E2E8F0;background:#F7F8FA;
              color:#1A202C;font-size:13px;margin-bottom:10px;
              outline:none;font-family:inherit; }
  .lm-input:focus { border-color:#00A878;background:#fff; }
  .lm-upload-area { border:2px dashed #B2F5EA;border-radius:12px;
                    padding:20px;text-align:center;background:#F8FFFD;
                    cursor:pointer;margin-bottom:8px;transition:all 0.15s; }
  .lm-upload-area:hover { border-color:#00A878;background:#E6FFFA; }
  .lm-upload-area.has-image { border-style:solid;border-color:#00A878; }
  .lm-preview { max-width:100%;max-height:180px;border-radius:8px;
                object-fit:contain;display:none; }
  .lm-upload-placeholder { color:#718096;font-size:13px; }
  .lm-btn-scan { width:100%;padding:10px;border-radius:999px;
                 border:1.5px solid #00A878;background:#fff;
                 color:#00A878;font-size:13px;font-weight:600;
                 cursor:pointer;margin-bottom:8px;transition:all 0.15s; }
  .lm-btn-scan:hover { background:#E6FFFA; }
  .lm-btn-scan:disabled { opacity:0.5;cursor:not-allowed; }
  .lm-btn-generate { width:100%;padding:14px;border-radius:999px;
                     border:none;background:linear-gradient(135deg,#00A878,#00875F);
                     color:#fff;font-size:15px;font-weight:700;
                     cursor:pointer;margin-top:4px;transition:all 0.15s; }
  .lm-btn-generate:hover { opacity:0.92; }
  .lm-btn-generate:disabled { opacity:0.5;cursor:not-allowed; }
</style>

<div id="lm">
  <!-- Header -->
  <div style="text-align:center;padding:20px 0 8px;">
    <div style="font-size:34px;">💊</div>
    <div style="font-size:26px;font-weight:800;color:#1A202C;margin-top:2px;">Legimed</div>
    <div style="font-size:13px;color:#718096;margin-top:4px;">
      Your medication, made legible</div>
  </div>

  <!-- Step 1: Profile -->
  <div class="lm-step">
    <div class="lm-step-num">1</div>
    <div class="lm-step-label">Your health profile</div>
  </div>
  <div class="lm-card">
    <div class="lm-label">Age group</div>
    <div class="lm-pill-group">
      <button class="lm-pill" onclick="setAge('child')">Child</button>
      <button class="lm-pill active" onclick="setAge('adult')">Adult</button>
      <button class="lm-pill" onclick="setAge('elderly')">Elderly</button>
    </div>
    <div class="lm-label">Sex</div>
    <div class="lm-pill-group">
      <button class="lm-pill active" onclick="setSex('male')">Male</button>
      <button class="lm-pill" onclick="setSex('female')">Female</button>
    </div>
    <div class="lm-label">Chronic conditions <span style="font-weight:400;">(tap to select)</span></div>
    <div class="lm-cond-grid">
      <button class="lm-cond" onclick="toggleCond(this,'heart_condition')">❤️ Heart disease</button>
      <button class="lm-cond" onclick="toggleCond(this,'diabetes')">🩸 Diabetes</button>
      <button class="lm-cond" onclick="toggleCond(this,'hypertension')">💉 Hypertension</button>
      <button class="lm-cond" onclick="toggleCond(this,'asthma')">🫁 Asthma</button>
      <button class="lm-cond" onclick="toggleCond(this,'kidney_issue')">🫘 Kidney</button>
      <button class="lm-cond" onclick="toggleCond(this,'liver_issue')">🫀 Liver</button>
      <button class="lm-cond" id="btn-pregnant" onclick="toggleCond(this,'pregnant')">🤰 Pregnant</button>
      <button class="lm-cond" id="btn-breastfeeding" onclick="toggleCond(this,'breastfeeding')">🍼 Breastfeeding</button>
    </div>
    <div class="lm-label">⚠️ Known allergies</div>
    <input class="lm-input" id="lm-allergies" type="text"
      placeholder="e.g. penicillin, sulfa, aspirin" oninput="sync()"/>
    <div class="lm-label">💊 Current medications</div>
    <input class="lm-input" id="lm-meds" type="text"
      placeholder="e.g. aspirin, metformin, lisinopril" oninput="sync()" style="margin-bottom:0;"/>
  </div>

  <!-- Step 2: Medication -->
  <div class="lm-step">
    <div class="lm-step-num">2</div>
    <div class="lm-step-label">Your medication</div>
  </div>
  <div class="lm-card">
    <div class="lm-label">📷 Scan medicine box (optional)</div>
    <div class="lm-upload-area" id="lm-drop" onclick="document.getElementById('lm-file').click()">
      <img id="lm-preview" class="lm-preview" src="" alt="preview"/>
      <div class="lm-upload-placeholder" id="lm-placeholder">
        <div style="font-size:24px;margin-bottom:6px;">📷</div>
        <div>Tap to upload or take photo</div>
        <div style="font-size:11px;color:#A0AEC0;margin-top:4px;">JPG, PNG, WEBP</div>
      </div>
    </div>
    <input type="file" id="lm-file" accept="image/*" capture="environment"
      style="display:none;" onchange="handleFile(this)"/>
    <button class="lm-btn-scan" id="lm-scan-btn" onclick="doScan()" disabled>
      🔍 Scan image</button>
    <div id="lm-scan-status" style="margin-bottom:8px;"></div>
    <div class="lm-label">💊 Drug name</div>
    <input class="lm-input" id="lm-drug" type="text"
      placeholder="Auto-filled after scan, or type here"
      oninput="sync()" style="margin-bottom:0;"/>
  </div>

  <!-- Step 3: Generate -->
  <div class="lm-step">
    <div class="lm-step-num">3</div>
    <div class="lm-step-label">Generate your guide</div>
  </div>
  <button class="lm-btn-generate" id="lm-gen-btn" onclick="doGenerate()">
    Generate my guide →</button>

  <div style="font-size:13px;font-weight:700;color:#1A202C;margin:14px 0 6px;">
    Your guide</div>
  <div id="lm-output"
    style="color:#718096;font-size:13px;padding:2rem 1rem;text-align:center;
           background:#fff;border-radius:14px;border:1.5px dashed #E2E8F0;">
    Complete the steps above to generate your guide.</div>

  <div style="text-align:center;padding:16px 0 4px;">
    <div style="font-size:10px;color:#A0AEC0;line-height:1.6;">
      Gemma 4 · NIH DailyMed · Apache 2.0 ·
      <a href="https://github.com/LorraineWong/legimed"
         style="color:#00A878;text-decoration:none;">GitHub</a>
    </div>
  </div>
</div>

<script>
var lm = {
  age_group:"adult", sex:"male",
  heart_condition:false, diabetes:false, hypertension:false, asthma:false,
  kidney_issue:false, liver_issue:false, pregnant:false, breastfeeding:false,
  allergies:"", other_meds:"", drug_name:"", img_b64:""
};

function setAge(v) {
  lm.age_group = v;
  document.querySelectorAll('.lm-pill-group:nth-of-type(1) .lm-pill').forEach(function(b){
    var active = b.textContent.trim().toLowerCase() === v;
    b.classList.toggle('active', active);
  });
  sync();
}

function setSex(v) {
  lm.sex = v;
  document.querySelectorAll('.lm-pill-group:nth-of-type(2) .lm-pill').forEach(function(b){
    var active = b.textContent.trim().toLowerCase() === v;
    b.classList.toggle('active', active);
  });
  var female = v === 'female';
  ['btn-pregnant','btn-breastfeeding'].forEach(function(id){
    var b = document.getElementById(id);
    if(b) b.style.opacity = female ? '1' : '0.4';
  });
  sync();
}

function toggleCond(btn, key) {
  lm[key] = !lm[key];
  btn.classList.toggle('active', lm[key]);
  sync();
}

function handleFile(input) {
  var file = input.files[0];
  if (!file) return;
  var reader = new FileReader();
  reader.onload = function(e) {
    var dataUrl = e.target.result;
    lm.img_b64 = dataUrl.split(',')[1];
    var preview = document.getElementById('lm-preview');
    var placeholder = document.getElementById('lm-placeholder');
    var drop = document.getElementById('lm-drop');
    preview.src = dataUrl;
    preview.style.display = 'block';
    placeholder.style.display = 'none';
    drop.classList.add('has-image');
    document.getElementById('lm-scan-btn').disabled = false;
    sync();
  };
  reader.readAsDataURL(file);
}

function sync() {
  lm.allergies = (document.getElementById('lm-allergies')||{}).value || '';
  lm.other_meds = (document.getElementById('lm-meds')||{}).value || '';
  lm.drug_name = (document.getElementById('lm-drug')||{}).value || '';
  // Push to Gradio hidden textboxes
  setGradio('lm-profile-state', JSON.stringify({
    age_group:lm.age_group, sex:lm.sex,
    heart_condition:lm.heart_condition, diabetes:lm.diabetes,
    hypertension:lm.hypertension, asthma:lm.asthma,
    kidney_issue:lm.kidney_issue, liver_issue:lm.liver_issue,
    pregnant:lm.pregnant, breastfeeding:lm.breastfeeding,
    allergies:lm.allergies, other_meds:lm.other_meds
  }));
  setGradio('lm-drug-state', lm.drug_name);
  setGradio('lm-img-state', lm.img_b64);
}

function setGradio(id, value) {
  var el = document.getElementById(id);
  if (!el) return;
  var input = el.querySelector('textarea, input');
  if (!input) return;
  var nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLTextAreaElement.prototype, 'value') ||
    Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value');
  if (nativeSetter && nativeSetter.set) {
    nativeSetter.set.call(input, value);
  } else {
    input.value = value;
  }
  input.dispatchEvent(new Event('input', {bubbles:true}));
}

function doScan() {
  var btn = document.getElementById('lm-scan-btn');
  var status = document.getElementById('lm-scan-status');
  if (!lm.img_b64) return;
  btn.disabled = true;
  btn.textContent = '⏳ Scanning…';
  status.innerHTML = '';
  sync();
  // Trigger Gradio scan button
  var gradioBtn = document.getElementById('lm-scan-trigger');
  if (gradioBtn) {
    var b = gradioBtn.querySelector('button');
    if (b) b.click();
  }
}

function doGenerate() {
  sync();
  var output = document.getElementById('lm-output');
  output.innerHTML = "<div style='text-align:center;padding:2rem;color:#00A878;'>" +
    "⏳ Generating your guide…<br>" +
    "<span style='font-size:11px;color:#718096;'>About 45 seconds</span></div>";
  var gradioBtn = document.getElementById('lm-gen-trigger');
  if (gradioBtn) {
    var b = gradioBtn.querySelector('button');
    if (b) b.click();
  }
}

// Watch Gradio output changes and mirror to our div
function watchOutput() {
  var el = document.getElementById('lm-gradio-output');
  if (!el) return;
  var observer = new MutationObserver(function() {
    var content = el.innerHTML;
    if (content && content.trim()) {
      document.getElementById('lm-output').innerHTML = content;
      // Reset scan button
      var btn = document.getElementById('lm-scan-btn');
      if (btn) { btn.disabled = false; btn.textContent = '🔍 Scan image'; }
    }
  });
  observer.observe(el, {childList:true, subtree:true, characterData:true});
}

// Watch scan status changes
function watchScanStatus() {
  var el = document.getElementById('lm-scan-status-gradio');
  if (!el) return;
  var observer = new MutationObserver(function() {
    var content = el.innerHTML;
    document.getElementById('lm-scan-status').innerHTML = content;
    // Update drug name if detected
    var strong = el.querySelector('strong');
    if (strong) {
      var drug = strong.textContent.trim();
      if (drug) {
        var input = document.getElementById('lm-drug');
        if (input) { input.value = drug; lm.drug_name = drug; sync(); }
      }
    }
    var btn = document.getElementById('lm-scan-btn');
    if (btn) { btn.disabled = false; btn.textContent = '🔍 Scan image'; }
  });
  observer.observe(el, {childList:true, subtree:true, characterData:true});
}

setTimeout(function() { watchOutput(); watchScanStatus(); sync(); }, 1000);
</script>
"""

    with gr.Blocks(title="Legimed", css=CSS) as demo:

        gr.HTML(UI_HTML)

        # Hidden Gradio state components
        profile_state = gr.Textbox(
            value='{}', visible=False, elem_id="lm-profile-state")
        drug_state = gr.Textbox(
            value='', visible=False, elem_id="lm-drug-state")
        img_state = gr.Textbox(
            value='', visible=False, elem_id="lm-img-state")

        # Hidden scan trigger button
        with gr.Row(visible=False, elem_id="lm-scan-trigger"):
            scan_btn = gr.Button("scan")

        # Hidden generate trigger button
        with gr.Row(visible=False, elem_id="lm-gen-trigger"):
            gen_btn = gr.Button("generate")

        # Hidden output (mirrored to HTML div by JS)
        scan_status_out = gr.HTML(value="", elem_id="lm-scan-status-gradio", visible=False)
        output = gr.HTML(value="", elem_id="lm-gradio-output", visible=False)

        scan_btn.click(
            fn=lambda img_b64, drug: _scan(img_b64, drug),
            inputs=[img_state, drug_state],
            outputs=[drug_state, scan_status_out]
        )

        gen_btn.click(
            fn=_generate,
            inputs=[drug_state, profile_state],
            outputs=output
        )

    return demo
