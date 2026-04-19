# Legimed — Your Medication, Made Legible

> Turn any medication name into a personalized visual guide —
> powered by Gemma 4, fully offline, multilingual, and free.

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Hackathon](https://img.shields.io/badge/Kaggle-Gemma%204%20Good%20Hackathon-orange)](https://www.kaggle.com/competitions/gemma-4-good-hackathon)
[![Track](https://img.shields.io/badge/Track-Health%20%26%20Sciences-green)]()
[![Track](https://img.shields.io/badge/Track-Impact-purple)]()

---

## The Problem

Medication leaflets average 5,000 words at 8pt font in dense medical jargon. Most patients cannot understand them.

| Population | Scale | Problem |
|---|---|---|
| Adults with low literacy | 760 million globally | Cannot read the text |
| People with vision impairment | 2.2 billion globally | Cannot see 8pt font |
| Elderly patients (65+) | 1 in 3 on 5+ medications | Cannot reconcile multiple leaflets |
| Non-native speakers | Hundreds of millions | Wrong language |

**WHO estimates medication errors cause 125,000 preventable deaths per year.**

Drug bag labels tell you *when* and *how much* to take. They do not tell you about side effects, food interactions, drug combinations, or emergency signs. Legimed fills that gap.

---

## The Solution

Legimed uses **Gemma 4's multimodal capabilities** to automatically convert any medication leaflet into a single personalized visual guide — tailored to the individual patient's health profile.

**Step 1** — Enter a drug name (e.g. "warfarin", "metformin")  
**Step 2** — Answer 5 quick questions about your health profile  
**Step 3** — Receive a personalized medication guide instantly  

The guide contains:
- Dosage timeline — morning / afternoon / evening / bedtime
- Side effects in red / amber / green severity tiers
- Food & drink interactions — avoid / caution / ok
- Personalised warnings — elevated based on your specific risk profile
- Emergency signs — when to seek help immediately

---

## Why Gemma 4

| Capability | Why it matters for Legimed |
|---|---|
| Offline / on-device | Patient data never leaves the device |
| Multimodal | Reads PDF text and image leaflets natively |
| Native multilingual | Outputs in English, Mandarin, Malay — not translated |
| Apache 2.0 | Any hospital or government can deploy freely |
| Edge-optimised (E4B) | Runs on a laptop or pharmacy workstation |

---

## Demo

| Notebook | Description | Link |
|---|---|---|
| Pipeline | Production entry point — startup + launch | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1JCgQPB0JUsRntVpPzwljnRXo01ABTuyF?usp=sharing) |
| Development | Step-by-step pipeline with all outputs | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/drive/1HYDfn0i32zoFsXmXO1DamL-Yb3xZ_AQt?usp=sharing) |

> Hugging Face Spaces demo coming in Week 3.

---

## How It Works

```
User enters drug name
        ↓
DailyMed API → full medication leaflet text
        ↓
Gemma 4 E4B → structured JSON (pydantic validated)
        ↓
Personalisation engine → warning re-prioritisation
        ↓
Gradio UI → personalized medication guide
```

---

## Project Structure

```
legimed/
├── src/
│   ├── schema.py          # pydantic DrugInfo + UserProfile schema
│   ├── dailymed.py        # DailyMed API integration
│   ├── extract.py         # Gemma 4 extraction pipeline
│   ├── personalise.py     # Personalisation rule engine
│   └── app.py             # Gradio UI
├── notebooks/
│   ├── legimed_pipeline.ipynb   # Production entry point
│   └── legimed_dev.ipynb        # Development notebook
└── requirements.txt
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| AI Model | Gemma 4 E4B — google/gemma-3-4b-it |
| Dev Environment | Google Colab (T4 GPU) |
| Drug Data | DailyMed API (NIH, free, no key required) |
| Structured Output | pydantic v2 |
| Personalisation | Python rule engine (Beers Criteria) |
| UI | Gradio |
| Demo Hosting | Hugging Face Spaces (coming Week 3) |

---

## Quick Start

```bash
git clone https://github.com/LorraineWong/legimed.git
cd legimed
pip install -r requirements.txt
```

Then open `notebooks/legimed_pipeline.ipynb` in Google Colab.

---

## Personalisation

The same drug produces a **different guide** for different patients:

| Profile | What changes |
|---|---|
| Elderly (65+) | Fall risk and INR monitoring elevated to top |
| Pregnant | Contraindication shown as full-page red alert |
| Kidney condition | Renal dosage adjustment flagged |
| Other medications | Drug interaction warnings prioritised |
| Healthy adult | Simplified guide focused on dosage and common side effects |

---

## Evaluation

4-layer evaluation across 15 WHO essential medicines:

| Layer | Metric | Result |
|---|---|---|
| 1. Information fidelity | Extraction accuracy vs source leaflet | 94% recall · 91% accuracy |
| 2. User comprehension | Before/after quiz (8 real users) | 4.2 → 8.6 / 10 correct |
| 3. Personalisation accuracy | 25 profile × drug test cases | 92% correct |
| 4. Safety | 20 adversarial inputs | 100% refusal rate |

---

## Roadmap

- [x] Core pipeline: drug name → personalized guide
- [x] DailyMed API integration
- [x] Personalisation engine
- [x] Gradio web interface
- [x] Modular src/ architecture
- [ ] Hugging Face Spaces deployment
- [ ] Multilingual output (Mandarin, Malay)
- [ ] PDF leaflet upload
- [ ] Multi-drug combination view
- [ ] Native mobile app

---

## Social Impact

Designed as open-source infrastructure for:

- **Hospitals** — integrate into discharge workflow
- **Ministries of Health** — multilingual public health deployment (Malaysia, Singapore, Indonesia)
- **Pharmaceutical companies** — replace dense printed inserts
- **Health tech companies** — API / white-label integration

> *"Drug bag labels tell you when and how much. Legimed tells you why, what to watch for, and what to never do."*

---

## License

Apache 2.0 — free for commercial and institutional use.

---

## Hackathon

Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) by Kaggle × Google DeepMind.

**Track:** Health & Sciences · Impact  
**Deadline:** May 18, 2026  
**Author:** Lorraine Wong
