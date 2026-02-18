#!/usr/bin/env python3
"""Debug: check if extending card crop captures EPIC."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract
from app.voters_pdf_processor import VotersPDFProcessor

pdf_path = "/Users/abc/Downloads/155-eroll/2026-EROLLGEN-S22-155-SIR-DraftRoll-Revision1-TAM-19-WI.pdf"

images = convert_from_path(pdf_path, dpi=300)
pil_img = images[3]  # Page 4 (0-indexed)
img = np.array(pil_img)
gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

cards = VotersPDFProcessor._detect_card_grid_from_image(gray)
print(f"Page 4: {len(cards)} cards")
print(f"Image size: {gray.shape}")

# Show first 3 cards with different crop extents
for i, (x, y, w, h) in enumerate(cards[:3]):
    print(f"\n--- Card {i+1} at ({x},{y},{w},{h}) ---")

    # Normal crop (just the card body)
    inset = 4
    card_img = gray[y + inset:y + h - inset, x + inset:x + w - inset]
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
    card_enhanced = clahe.apply(card_img)
    text = pytesseract.image_to_string(card_enhanced, lang="tam+eng", config="--oem 3 --psm 6")
    print(f"Normal crop: {text[:200].replace(chr(10), ' | ')}")

    # Extended crop (include header area above)
    header_extend = min(55, y - 5)
    y_start = max(0, y - header_extend)
    ext_img = gray[y_start:y + h - inset, x + inset:x + w - inset]
    ext_enhanced = clahe.apply(ext_img)
    ext_text = pytesseract.image_to_string(ext_enhanced, lang="tam+eng", config="--oem 3 --psm 6")
    print(f"Extended crop (y={y_start}→{y+h-inset}): {ext_text[:300].replace(chr(10), ' | ')}")

    # Try PSM 3 on extended crop for EPIC
    ext_text_psm3 = pytesseract.image_to_string(ext_enhanced, lang="tam+eng", config="--oem 3 --psm 3")
    print(f"Extended PSM 3: {ext_text_psm3[:300].replace(chr(10), ' | ')}")

    # Check if EPIC pattern found
    import re
    epics = re.findall(r'[A-Z]{3}\d{7}', ext_text + ext_text_psm3)
    print(f"EPICs found: {epics}")
