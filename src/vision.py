"""
vision.py — Image input pipeline for Legimed.
Primary: Gemini API vision extracts drug name from photo.
Fallback: Tesseract OCR + heuristic.
"""

import re
import os
from PIL import Image
import google.generativeai as genai

genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
vision_model = genai.GenerativeModel("gemini-2.0-flash")


def preprocess_image(pil_image: Image.Image) -> Image.Image:
    """Resize to max 1024px on longest side, convert to RGB."""
    img = pil_image.convert("RGB")
    max_side = 1024
    w, h = img.size
    if max(w, h) > max_side:
        scale = max_side / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return img


def extract_drug_name_gemini(pil_image: Image.Image) -> str:
    """
    Use Gemini API vision to extract drug name from medication box photo.
    Returns drug name string, or empty string if not found.
    """
    img = preprocess_image(pil_image)

    prompt = "What is the drug name or medicine name shown on this box? Reply with ONLY the drug name (e.g. Panadol, Warfarin, Metformin). Do not include dosage, brand taglines, or manufacturer. If you cannot read a drug name, reply UNKNOWN."

    response = vision_model.generate_content([prompt, img])
    drug_name = response.text.strip().split("\n")[0].strip()
    drug_name = re.sub(r'\s+\d+\s*(mg|mcg|ml|%|iu).*$', '', drug_name, flags=re.IGNORECASE).strip()

    if not drug_name or drug_name.upper() == "UNKNOWN" or len(drug_name) > 50:
        return ""

    return drug_name


def extract_text_tesseract(pil_image: Image.Image) -> str:
    """Fallback: Tesseract OCR. Returns empty string if unavailable."""
    try:
        import pytesseract
        img = preprocess_image(pil_image)
        try:
            return pytesseract.image_to_string(img, lang="eng+chi_sim").strip()
        except Exception:
            return pytesseract.image_to_string(img, lang="eng").strip()
    except Exception as e:
        print(f"[vision] Tesseract not available: {e}")
        return ""


def guess_drug_name_from_text(text: str) -> str:
    """Heuristic drug name extraction from raw OCR text."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""

    penalty_words = [
        "take", "store", "keep", "batch", "exp", "mfg", "www",
        "tel", "fax", "ltd", "inc", "warning", "caution",
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
        if clean.isupper() and word_count <= 4:
            score += 4
        elif clean.istitle():
            score += 2
        if any(w in clean.lower() for w in penalty_words):
            score -= 5
        if re.search(r'\d+\s*(mg|mcg|ml|%|iu)', line, re.IGNORECASE):
            score += 3
        if score > best_score:
            best_score = score
            best = " ".join(clean.split()[:3])

    return re.sub(r'\s+\d+$', '', best).strip()


def image_to_drug_name(pil_image: Image.Image, model=None, tokenizer=None, processor=None) -> tuple[str, str]:
    """
    Main entry point for image input.
    Primary: Gemini API vision.
    Fallback: Tesseract OCR + heuristic.
    Returns: (drug_name, method_used)
    """
    print("[vision] Using Gemini API vision to identify drug...")
    try:
        drug_name = extract_drug_name_gemini(pil_image)
        if drug_name:
            print(f"[vision] Gemini identified: {drug_name}")
            return drug_name, "gemini"
        else:
            print("[vision] Gemini returned empty, falling back to Tesseract...")
    except Exception as e:
        print(f"[vision] Gemini vision failed: {e}, falling back to Tesseract...")

    raw_text = extract_text_tesseract(pil_image)
    drug_name = guess_drug_name_from_text(raw_text)
    method = "tesseract" if drug_name else "failed"
    return drug_name, method
