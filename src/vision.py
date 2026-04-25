"""
vision.py — Image input pipeline for Legimed.
Primary: Gemma 4 multimodal vision extracts drug name directly from photo.
Fallback: Tesseract OCR + heuristic if model not available.
"""

import re
from PIL import Image


def tesseract_status() -> tuple[bool, str]:
    """Check Tesseract availability and return (ok, message)."""
    try:
        import pytesseract
        version = pytesseract.get_tesseract_version()
        langs = pytesseract.get_languages(config='')
        missing = [l for l in ["eng", "chi_sim"] if l not in langs]
        if missing:
            return False, f"Tesseract found (v{version}) but missing language packs: {missing}."
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


def extract_drug_name_gemma(pil_image: Image.Image, model, tokenizer, processor) -> str:
    """
    Use Gemma 4 vision to extract drug name from medication box photo.
    Requires a preloaded multimodal processor to avoid runtime OOM in Colab.
    Returns drug name string, or empty string if not found.
    """
    import torch

    prompt = """Look at this medication box or label photo.
What is the drug name or medicine name shown on this box?
Reply with ONLY the drug name (e.g. "Panadol", "Warfarin", "Metformin").
Do not include dosage, brand taglines, or manufacturer.
If you cannot read a drug name, reply UNKNOWN."""

    inputs = processor(
        text=prompt,
        images=preprocess_image(pil_image),
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=20,
            temperature=0,
            do_sample=False,
        )

    response = tokenizer.decode(
        outputs[0][inputs["input_ids"].shape[-1]:],
        skip_special_tokens=True,
    ).strip()

    drug_name = response.strip().split("\n")[0].strip()
    drug_name = re.sub(r'\s+\d+\s*(mg|mcg|ml|%|iu).*$', '', drug_name, flags=re.IGNORECASE).strip()

    if not drug_name or drug_name.upper() == "UNKNOWN" or len(drug_name) > 50:
        return ""

    return drug_name


def extract_text_tesseract(pil_image: Image.Image) -> str:
    """Fallback: Tesseract OCR. Returns empty string if unavailable."""
    ok, msg = tesseract_status()
    if not ok:
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
    """Heuristic drug name extraction from raw OCR text."""
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

        if re.match(r'^[A-Za-z][A-Za-z\s\-]+$', clean) and word_count <= 3:
            score += 2

        if score > best_score:
            best_score = score
            best = " ".join(clean.split()[:3])

    best = re.sub(r'\s+\d+$', '', best).strip()
    return best


def image_to_drug_name(pil_image: Image.Image, model=None, tokenizer=None, processor=None) -> tuple[str, str]:
    """
    Main entry point for image input.
    Primary: Gemma 4 vision (if model provided).
    Fallback: Tesseract OCR + heuristic.

    Returns:
        (drug_name, method_used)
        drug_name: best guess, empty string if failed
        method_used: "gemma" | "tesseract" | "failed"
    """
    if model is not None and tokenizer is not None and processor is not None:
        print("[vision] Using Gemma 4 vision to identify drug...")
        try:
            drug_name = extract_drug_name_gemma(pil_image, model, tokenizer, processor)
            if drug_name:
                print(f"[vision] Gemma identified: {drug_name}")
                return drug_name, "gemma"
            else:
                print("[vision] Gemma returned empty, falling back to Tesseract...")
        except Exception as e:
            print(f"[vision] Gemma vision failed: {e}, falling back to Tesseract...")

    raw_text = extract_text_tesseract(pil_image)
    drug_name = guess_drug_name_from_text(raw_text)
    method = "tesseract" if drug_name else "failed"
    return drug_name, method


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
