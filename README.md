# Legimed — Your Medication, Made Legible

> Turn any medication name into a personalized visual guide —
> powered by Gemma 4, fully offline, multilingual, and free.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Hackathon](https://img.shields.io/badge/Kaggle-Gemma%204%20Good%20Hackathon-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
[![Track](https://img.shields.io/badge/Track-Health%20%26%20Sciences-green)]()
[![Track](https://img.shields.io/badge/Track-Impact-purple)]()

---

## The Problem

Medication leaflets average 5,000 words at 8pt font in dense medical jargon.

| Population | Scale | Problem |
|---|---|---|
| Adults with low literacy | 760 million globally | Cannot read the text |
| People with vision impairment | 2.2 billion globally | Cannot see 8pt font |
| Elderly patients (65+) | 1 in 3 on 5+ medications | Cannot reconcile multiple leaflets |
| Non-native speakers | Hundreds of millions | Wrong language |

**WHO estimates medication errors cause 125,000 preventable deaths per year.**

Drug bag labels tell you *when* and *how much* to take. They do not tell you about side effects, food interactions, emergency signs, or what specifically matters for *your* health profile. Legimed fills that gap.

---

## The Solution

Legimed uses **Gemma 4** to automatically convert any medication name into a personalized visual guide — tailored to the individual patient's health profile.

**Step 1** — Enter a drug name (e.g. "warfarin", "metformin")
**Step 2** — Select your health profile (age, conditions, other medications)
**Step 3** — Receive a personalized medication guide instantly

The guide contains:
- **Personal summary** — 3 plain-English sentences written specifically for your profile
- **Dosage timeline** — morning / afternoon / evening / bedtime visual grid
- **Side effects** — red / amber / green severity tiers with clear actions
- **Food & drink** — avoid / caution / ok chips
- **Personalised warnings** — elevated based on your specific risk profile
- **Emergency signs** — when to seek help immediately

---

## Why Gemma 4

| Capability | Why it matters for Legimed |
|---|---|
| Offline / on-device | Patient data never leaves the device |
| Structured extraction | Reads medication leaflets and outputs validated JSON |
| Native multilingual | Outputs in English, Mandarin, Malay — not translated |
| Apache 2.0 | Any hospital or government can deploy freely |
| Edge-optimised (E4B) | Runs on a laptop or pharmacy workstation |

---

## Demo

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1JCgQPB0JUsRntVpPzwljnRXo01ABTuyF?usp=sharing)

Open the notebook in Google Colab (free T4 GPU), run all cells in order, and a public Gradio link will be generated.

> Hugging Face Spaces permanent deployment coming soon.

---

## How It Works

```
User enters drug name
        ↓
DailyMed API (NIH) → full medication leaflet text
        ↓
Gemma 4 E4B → structured JSON extraction (pydantic validated)
        ↓
Personalisation engine → warning re-prioritisation by health profile
        ↓
Python summary generator → 3-sentence plain-English personal summary
        ↓
Gradio UI → card-based visual medication guide
```

---

## Technical Architecture

```
legimed/
├── src/
│   ├── schema.py          # pydantic DrugInfo + UserProfile models
│   ├── dailymed.py        # NIH DailyMed API integration
│   ├── extract.py         # Gemma 4 extraction pipeline
│   ├── personalise.py     # Personalisation engine + summary generator
│   └── app.py             # Gradio UI with card-based HTML output
└── requirements.txt
```

---

## Running Locally

### Requirements
- Python 3.10+
- GPU with 15GB+ VRAM (e.g. NVIDIA T4) — or use the Colab link above
- Hugging Face account with Gemma 4 access

### Setup

```bash
git clone https://github.com/LorraineWong/legimed.git
cd legimed
pip install -r requirements.txt
```

### Run

```python
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch, sys

sys.path.insert(0, 'src')

tokenizer = AutoTokenizer.from_pretrained("google/gemma-3-4b-it")
model = AutoModelForCausalLM.from_pretrained(
    "google/gemma-3-4b-it",
    torch_dtype=torch.bfloat16,
    device_map="auto"
)

from app import build_demo
demo = build_demo(model, tokenizer)
demo.launch()
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Gemma 4 E4B — google/gemma-3-4b-it |
| Dev Environment | Google Colab (T4 GPU) |
| Drug Data | NIH DailyMed API (free, no API key required) |
| Structured Output | pydantic v2 |
| Personalisation | Python rule engine |
| UI | Gradio with card-based HTML output |
| Demo Hosting | Hugging Face Spaces (coming soon) |

---

## Personalisation

The same drug produces a **different guide** for different patients:

| Profile | What changes |
|---|---|
| Senior (65+) | Fall risk and INR monitoring elevated to top |
| Pregnant | Contraindication shown as top priority warning |
| Kidney condition | Renal processing note added to summary |
| Other medications | Drug interaction warnings prioritised |
| Healthy adult | Simplified guide focused on dosage and common side effects |

---

## Roadmap

- [x] Core pipeline: drug name → personalized visual guide
- [x] NIH DailyMed API integration
- [x] Personalisation engine
- [x] Card-based HTML infographic output
- [x] Personal summary generation
- [x] Gradio web interface
- [ ] Hugging Face Spaces permanent deployment
- [ ] Image input — scan drug box photo (Gemma 4 vision)
- [ ] Multilingual output (Mandarin, Malay)
- [ ] Drug interaction detection across multiple medications
- [ ] Medication reminders (v2.0)
- [ ] Course tracker — when to stop or refill (v2.0)
- [ ] Family medication profiles (v2.0)

---

## Social Impact

Designed as open-source infrastructure for:

- **Hospitals** — integrate into patient discharge workflow
- **Ministries of Health** — multilingual public health deployment
- **Pharmaceutical companies** — replace dense printed inserts
- **Health tech companies** — API / white-label integration

> *"Drug bag labels tell you when and how much. Legimed tells you why, what to watch for, and what to never do — in plain language you can actually understand."*

---

## License

Apache 2.0 — free for commercial and institutional use.

---

## Hackathon

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) by Kaggle × Google DeepMind.

**Track:** Health & Sciences · Impact
**Deadline:** May 18, 2026
**Author:** Lorraine Wong
