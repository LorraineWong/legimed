"""
vision.py — Image input pipeline for Legimed.
Tesseract OCR extracts text from drug box photo.
Extracted text is passed to Gemma 4 for processing.
Gemma 4 remains the core AI engine (hackathon compliant).
"""

import re
from PIL import Image


def _tesseract_available() -> bool:
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


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
    Returns raw text string for Gemma 4 to process downstream.
    Raises RuntimeError if Tesseract is not installed.
    """
    if not _tesseract_available():
        raise RuntimeError(
            "Tesseract not installed. Run install_tesseract_colab() first."
        )

    import pytesseract
    img = preprocess_image(pil_image)

    try:
        text = pytesseract.image_to_string(img, lang="eng+chi_sim+msa")
    except pytesseract.TesseractError:
        text = pytesseract.image_to_string(img, lang="eng")

    return text.strip()


def guess_drug_name_from_text(text: str) -> str:
    """
    Heuristic extraction of drug name from raw OCR text.
    Drug names tend to appear in the first lines, ALL CAPS or Title Case,
    short (1-3 words), near dosage markers like mg/mcg/ml.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""

    best = ""
    best_score = -1

    penalty_words = [
        "take", "tablet", "capsule", "store", "keep", "batch",
        "exp", "mfg", "www", "tel", "fax", "ltd", "inc", "ptd",
        "warning", "caution", "directions", "ingredients"
    ]

    for line in lines[:15]:
        score = 0
        clean = re.sub(r'[®™©]', '', line).strip()
        if not clean or len(clean) < 2:
            continue

        word_count = len(clean.split())
        if word_count <= 3:
            score += 3
        elif word_count <= 5:
            score += 1
        else:
            score -= 2

        if clean.isupper():
            score += 2
        elif clean.istitle():
            score += 1

        if any(w in clean.lower() for w in penalty_words):
            score -= 3

        if re.search(r'\d+\s*(mg|mcg|ml|%|iu)', line, re.IGNORECASE):
            score += 2

        if score > best_score:
            best_score = score
            best = " ".join(clean.split()[:3])

    return best


def image_to_drug_name(pil_image: Image.Image) -> str:
    """
    Main entry point for image tab.
    Photo -> Tesseract OCR -> heuristic drug name extraction.
    Returns drug name string ready to pass to get_drug_leaflet().
    """
    text = extract_text_from_image(pil_image)
    drug_name = guess_drug_name_from_text(text)
    if not drug_name:
        return text[:100]
    return drug_name


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
