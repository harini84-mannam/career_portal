# extract plain text from a loaded document
# use the existing text layer for digital PDFs and text files since it's
# faster and more accurate than OCR
# for scanned PDFs or images, preprocess the pages and run OCR instead

import os
import shutil
import pytesseract
from .image_processing import preprocess_pipeline

DIGITAL_TEXT_THRESHOLD = 40

# BUG FIX: pytesseract.tesseract_cmd was never being set anywhere in this
# project. On Linux/Mac, pytesseract usually finds tesseract fine because
# it's on PATH after an apt/brew install. On Windows though, the installer
# does NOT reliably add tesseract.exe to PATH, so pytesseract throws
# `TesseractNotFoundError` the moment OCR actually runs on an image or a
# scanned PDF (digital PDFs and .txt files never hit this code path, which
# is why it can look like "everything works" until someone uploads a
# photographed/scanned resume).
#
# Resolution order:
#   1. explicit TESSERACT_CMD env var (set this to override on any machine)
#   2. whatever's already on PATH (works out of the box on Linux/Mac/CI)
#   3. the default Windows install locations, including the per-user
#      AppData path that the Windows installer uses when it's installed
#      "for me only" rather than system-wide
def _resolve_tesseract_cmd() -> str:
    env_override = os.environ.get("TESSERACT_CMD")
    if env_override and os.path.exists(env_override):
        return env_override

    on_path = shutil.which("tesseract")
    if on_path:
        return on_path

    candidates = [
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path

    return ""  # nothing found - let pytesseract raise its normal error


_resolved_cmd = _resolve_tesseract_cmd()
if _resolved_cmd:
    pytesseract.pytesseract.tesseract_cmd = _resolved_cmd

_easyocr_reader = None


def _get_easyocr_reader():
# EasyOCR is optional, so only import and initialize it when
# it's actually requested
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["en"], gpu=False)
    return _easyocr_reader


def ocr_image(img, engine: str = "tesseract") -> str:
    # cleans up the image with opencv first, then runs OCR on it
    processed = preprocess_pipeline(img)
    if engine == "easyocr":
        reader = _get_easyocr_reader()
        results = reader.readtext(processed, detail=0, paragraph=True)
        return "\n".join(results)
# default OCR engine - Tesseract
    config = "--oem 3 --psm 6"
    return pytesseract.image_to_string(processed, config=config)


def extract_text(doc: dict, engine: str = "tesseract") -> str:
    # decide whether to use the document's existing text layer
    # or run OCR on its page image
    digital_text = doc.get("digital_text", "") or ""
    if doc["type"] in ("text",):
        return digital_text

    if doc["type"] == "pdf" and len(digital_text.strip()) >= DIGITAL_TEXT_THRESHOLD:
    # digital PDF has enough text, so skip OCR
            return digital_text

    page_texts = []
    for img in doc.get("page_images", []):
        try:
            page_texts.append(ocr_image(img, engine=engine))
        except Exception:
            page_texts.append("")
    ocr_text = "\n".join(page_texts).strip()
    # if OCR extracted less text than the original text layer,
    # fall back to the digital text instead
    if len(ocr_text) < len(digital_text):
        return digital_text
    return ocr_text