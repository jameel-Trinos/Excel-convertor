#!/usr/bin/env python3
"""Debug: show OCR text from individual cards on specific pages."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cv2
import numpy as np
from pdf2image import convert_from_path
import pytesseract
from app.voters_pdf_processor import VotersPDFProcessor

pdf_path = "/Users/abc/Downloads/155-eroll/2026-EROLLGEN-S22-155-SIR-DraftRoll-Revision1-TAM-19-WI.pdf"

images = convert_from_path(pdf_path, dpi=300)
print(f"Total pages: {len(images)}")

# Check specific pages: page 4 (first voter page), page 17 (single card page)
for page_idx in [3, 16, 23]:  # 0-indexed: page 4, 17, 24
    pil_img = images[page_idx]
    img = np.array(pil_img)
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)

    cards = VotersPDFProcessor._detect_card_grid_from_image(gray)
    print(f"\n{'='*60}")
    print(f"Page {page_idx+1}: {len(cards)} cards detected")
    print(f"Image size: {gray.shape}")
    print(f"{'='*60}")

    # Show first 3 cards text
    for i, (x, y, w, h) in enumerate(cards[:3]):
        inset = 4
        card_img = gray[y + inset:y + h - inset, x + inset:x + w - inset]
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(4, 4))
        card_enhanced = clahe.apply(card_img)

        card_text = pytesseract.image_to_string(
            card_enhanced, lang="tam+eng",
            config="--oem 3 --psm 6",
        )
        print(f"\n--- Card {i+1} at ({x},{y},{w},{h}) ---")
        print(card_text[:300])
        print(f"---")

    # If page 17, also try full page OCR
    if page_idx == 16:
        print(f"\n--- Full page 17 OCR (PSM 3) ---")
        full_text = pytesseract.image_to_string(gray, lang="tam+eng", config="--oem 3 --psm 3")
        print(full_text[:500])
