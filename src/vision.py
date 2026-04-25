"""
vision.py — Image input pipeline for Legimed.
Tesseract OCR extracts text from drug box photo.
Extracted text is passed to Gemma 4 for processing.
Gemma 4 remains the core AI engine (hackathon compliant).
"""

import re
from PIL import Image


def tesseract_status() -> tuple[bool, str]:
    """
    Check Tesseract availability and return (ok, message).
    Call this at Gradio launch time to surface problems early.
    """
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        # Check which language packs are available
        langs = pytesseract.get_languages(config='')
        missing = [l for l in ["eng", "chi_sim"] if l not in langs]
        if missing:
            return False, f"Tesseract found (v{version}) but missing language packs: {missing}. Run install_tesseract_colab()."
        return True, f"Tesseract OK (v{version}), langs: {langs}"
    except Exception as e:
        return False, f"Tesseract not available: {e}"


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """Resize to max 1024px on longest side, convert to RGB."""
    img = pil_image.convert("RGB")
    max_side = 1024
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def extract_text_from_image(pil_image: Image.Image) -> str:
    """
    Extract all visible text from a medication photo using Tesseract OCR.
    Returns raw text string. Returns empty string (not raises) if Tesseract unavailable.
    """
    ok, msg = tesseract_status()
    if not ok:
        # Return empty string — caller will handle gracefully
        print(f"[vision] {msg}")
        return ""

    import pytesseract
    img = preprocess_image(pil_image)

    try:
        text = pytesseract.image_to_string(img, lang="eng+chi_sim")
    except Exception:
        try:
            text = pytesseract.image_to_string(img, lang="eng")
        except Exception as e:
            print(f"[vision] OCR failed: {e}")
            return ""

    return text.strip()


def guess_drug_name_from_text(text: str) -> str:
    """
    Extract drug name from raw OCR text.
    Strategy:
      1. Look for lines near dosage markers (mg/mcg/ml) — highest confidence
      2. Look for ALL CAPS or Title Case short lines in first 20 lines
      3. Fall back to first non-empty line if nothing scores well
    Penalty words filter out instructions, addresses, batch info.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""

    penalty_words = [
        "take", "store", "keep", "batch", "exp", "mfg", "www",
        "tel", "fax", "ltd", "inc", "ptd", "warning", "caution",
        "directions", "ingredients", "manufactured", "distributed",
        "each", "contains", "read", "leaflet", "patient"
    ]

    best = ""
    best_score = -99

    for i, line in enumerate(lines[:20]):
        score = 0
        clean = re.sub(r'[®™©,.\-_|]', ' ', line).strip()
        clean = re.sub(r'\s+', ' ', clean).strip()
        if not clean or len(clean) < 2:
            continue

        # Lines appearing earlier on the label are more likely the drug name
        if i < 3:
            score += 3
        elif i < 6:
            score += 1

        word_count = len(clean.split())
        if word_count <= 2:
            score += 4
        elif word_count <= 4:
            score += 2
        elif word_count > 6:
            score -= 2

        # ALL CAPS short line = strong drug name signal
        if clean.isupper() and word_count <= 4:
            score += 4
        elif clean.istitle():
            score += 2

        # Penalise instruction-like lines
        if any(w in clean.lower() for w in penalty_words):
            score -= 5

        # Bonus: dosage marker on same line (e.g. "Warfarin 5mg")
        if re.search(r'\d+\s*(mg|mcg|ml|%|iu)', line, re.IGNORECASE):
            score += 3

        # Bonus: looks like a drug name pattern (letters only, possibly with numbers)
        if re.match(r'^[A-Za-z][A-Za-z\s\-]+$', clean) and word_count <= 3:
            score += 2

        if score > best_score:
            best_score = score
            # Take first 1-3 words only as the drug name
            best = " ".join(clean.split()[:3])

    # Strip trailing dosage if attached: "Warfarin 5" -> "Warfarin"
    best = re.sub(r'\s+\d+$', '', best).strip()

    return best


def image_to_drug_name(pil_image: Image.Image) -> tuple[str, str]:
    """
    Main entry point for image tab.
    Photo -> Tesseract OCR -> heuristic drug name extraction.

    Returns:
        (drug_name, raw_ocr_text)
        drug_name: best guess at drug name, empty string if failed
        raw_ocr_text: full OCR output for debugging / user review
    """
    raw_text = extract_text_from_image(pil_image)
    drug_name = guess_drug_name_from_text(raw_text)
    return drug_name, raw_text


def install_tesseract_colab():
    """Install Tesseract + language packs in Google Colab. Run once per session."""
    import subprocess
    print("Installing Tesseract OCR...")
    subprocess.run(
        ["apt-get", "install", "-q", "-y",
         "tesseract-ocr", "tesseract-ocr-chi-sim", "tesseract-ocr-msa"],
        check=True
    )
    subprocess.run(["pip", "install", "-q", "pytesseract"], check=True)
    print("Done.")
