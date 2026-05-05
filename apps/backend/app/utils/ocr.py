import io
from typing import Optional, Tuple
import pytesseract
from PIL import Image


def extract_text_from_bytes(image_bytes: bytes) -> Tuple[Optional[str], float]:
    """
    Extract text and average confidence from raw image bytes.
    Returns (text, confidence) where confidence is 0.0–1.0.
    Processes image entirely in memory — nothing is written to disk.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode not in ("L", "RGB"):
            img = img.convert("RGB")

        data = pytesseract.image_to_data(
            img,
            lang="eng+por",
            config="--psm 6",
            output_type=pytesseract.Output.DICT,
        )

        words = [
            (data["text"][i], int(data["conf"][i]))
            for i in range(len(data["text"]))
            if int(data["conf"][i]) > 0 and data["text"][i].strip()
        ]

        if not words:
            return None, 0.0

        text = " ".join(w for w, _ in words).strip()
        avg_conf = sum(c for _, c in words) / len(words) / 100.0
        return (text if text else None), avg_conf

    except Exception as exc:
        print(f"OCR bytes error: {exc}")
        return None, 0.0


def extract_text_from_image(image_path: str) -> Optional[str]:
    """
    Extract text from image using Tesseract OCR.
    Supports multiple languages (English and Portuguese).
    """
    try:
        # Open image
        image = Image.open(image_path)
        
        # Convert to RGB if necessary
        if image.mode not in ('L', 'RGB'):
            image = image.convert('RGB')
        
        # Run OCR with multiple languages
        text = pytesseract.image_to_string(
            image,
            lang='eng+por',  # English + Portuguese
            config='--psm 6'  # Page segmentation mode: assume uniform block of text
        )
        
        # Clean up text
        text = text.strip()
        
        # Remove extra whitespace
        text = ' '.join(text.split())
        
        return text if text else None
        
    except Exception as e:
        print(f"OCR Error: {e}")
        return None
