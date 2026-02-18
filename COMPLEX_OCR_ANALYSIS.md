# Complex OCR PDF Analysis

This document describes how to analyze complex OCR / image-based election PDFs with the current pipeline and what failure modes to look for.

## Running the analysis script

From the **backend** directory:

```bash
cd backend
python analyze_complex_ocr_pdf.py <path_to_pdf> [output.json]
```

Examples:

```bash
# Analyze a PDF and print summary to stdout
python analyze_complex_ocr_pdf.py /path/to/AC215_Tirichendur.pdf

# Save summary to a JSON file for inspection
python analyze_complex_ocr_pdf.py /path/to/AC215_Tirichendur.pdf analysis_result.json
```

You can place a copy of the sample PDF in the project (e.g. `backend/examples/AC215_sample.pdf`) and run:

```bash
python analyze_complex_ocr_pdf.py examples/AC215_sample.pdf
```

## What the script reports

- **Detection**: PDF type (text / image / mixed), confidence, page counts.
- **Extraction method**: Whether grid OCR or full-page OCR (bbox) was used.
- **Merged table**: Column count, row count, header sample, confidence score.
- **Validation**: Pass/fail, confidence, and a sample of validation issues (e.g. OCR character errors, column count).
- **Failure-mode hints**: Short notes such as "Very few columns", "Validation failed", "OCR path used with possible column drift".

## Failure modes to watch for

| Failure mode | What you might see | Next step |
|-------------|--------------------|-----------|
| **Grid not found** | Extraction method is OCR but table has very few columns or rows; or logs say "No grid detected". | Fallback is bbox parsing; improve grid detection (binarization, kernel ratios, DPI) or rely on bbox improvements (column boundaries from page 1). |
| **Wrong column count on later pages** | Merged table has fewer columns than page 1, or rows with inconsistent length. | Enforce expected column count from page 1; normalize row length (pad/trim) and log trimming. |
| **Missing cell data** | Validation reports many issues; or manual check shows empty cells or merged values in wrong column. | Improve grid line detection for faint lines; or improve bbox column assignment (X-ranges from page 1). |
| **Header row misdetected** | First data row treated as header, or header split across rows. | Use election-aware header detection; optional AI structure step to identify header row index. |
| **Low OCR confidence** | Validation confidence low; many "potential OCR error" issues. | Increase DPI for complex mode; optional AI structure correction. |

## Sample PDF (AC215 Tiruchendur)

The reference sample is a 7-page election result PDF. For implementation and regression testing, copy it into the repo (e.g. `backend/examples/`) so the analysis script can be run without depending on Cursor workspace paths.
