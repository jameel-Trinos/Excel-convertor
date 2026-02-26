# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDF to Excel Converter — a full-stack application for converting tabular PDFs (primarily Indian election documents) to professionally formatted Excel spreadsheets. Supports AI-enhanced and deterministic (no-AI) processing, OCR for scanned documents, and specialized pipelines for election results, booth data, constituency data, and voter roll extraction.

## Development Commands

### Backend (FastAPI/Python)
```bash
cd backend
source ../.venv/bin/activate        # Root-level venv (recommended)
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### Frontend (Next.js/TypeScript)
```bash
cd frontend
npm install
npm run dev          # Dev server on port 3000
npm run build        # Production build
npm run lint         # ESLint
```

### System Dependencies (required before backend install)
```bash
# macOS
brew install ghostscript openjdk tesseract poppler libmagic
# Ubuntu
sudo apt-get install ghostscript default-jre tesseract-ocr poppler-utils libmagic1
```

### Testing
```bash
# From project root
python test_claude.py                    # Claude AI integration test
python test_convert_endpoint.py          # /api/convert endpoint test
python test_deterministic_parser.py      # Deterministic pipeline test
./verify_setup.sh                        # Verify system dependencies

# PyTest suite (from backend/ directory)
cd backend && pytest                     # All tests
cd backend && pytest tests/test_specific.py  # Single test file

# Backend-specific tests (from backend/ directory)
python test_party_normalizer.py
python test_header_extractor.py
python test_column_filter.py
python test_ocr_setup.py

# Validate Excel output
python backend/recalc.py output.xlsx
```

### Docker
```bash
docker-compose up -d      # Start backend (8000) + frontend (3000)
docker-compose down        # Stop services
```

## Architecture

### High-Level Data Flow

All pipelines follow: **Upload PDF → Extract tables → Process/Format → Generate Excel → Download**

The backend is a single FastAPI app (`backend/app/main.py`, ~3300 lines) with all endpoints defined directly (no routers). State is stored in-memory via `task_store.py` (dicts for tasks, geocode_tasks, translation_tasks, voter_convert_jobs, bulk_voter_jobs). Progress is streamed to the frontend via SSE.

### Five Processing Pipelines

1. **Election Results** (`/api/upload`) — Primary pipeline. PDFProcessor auto-detects text vs image PDFs, extracts tables via pdfplumber/camelot/tabula (text) or grid OCR (image). If AI keys are present, Claude/OpenAI standardizes headers; otherwise deterministic rules apply. Output goes through ExcelCreator with professional formatting.

2. **Booth Data** (`/api/booth/upload`) — Same PDFProcessor extraction as election results but uses booth-specific Excel formatting. Has a dedicated `/api/booth/add-booth-name-column` endpoint for extracting booth names from parenthetical descriptors.

3. **Constituency Data** — Routed through ConstituencyProcessor → ConstituencyExcelCreator. Handles assembly constituency-level election data with specialized text parsing.

4. **Voter Extraction** (`/api/voters/upload`, `/api/voters/convert-pdf`) — Extracts individual voter records from Indian electoral roll PDFs. Uses per-card OCR strategy: detect cards on page → crop each card → PaddleOCR (Tamil+English) → post-correction for EPIC/age/gender fields. Supports single file and bulk upload (`/api/voters/bulk-upload/*`).

5. **Excel Merge** (`/api/excel-merge`) — Merges multiple Excel files into one.

### Cross-Cutting Features

- **Column Filtering** (`/api/filter-columns`, `/api/filter-excel`) — Select/reorder columns in output Excel via ColumnFilterService
- **Party Name Normalization** (`/api/normalize-column`) — Tamil Nadu political party name standardization via PartyNormalizer
- **Translation** (`/api/translate/start`) — Translate Excel to Tamil/Hindi/English via TranslationService (deep-translator)
- **Geocoding** (`/api/geocode/start`) — Address geocoding via GeocodingService (geopy)

### OCR Strategy (scanned/image PDFs)

1. `pdf_detector.py` classifies PDF as TEXT, IMAGE, or MIXED
2. `grid_ocr_processor.py` — primary: detects table grid lines with OpenCV morphology, OCRs individual cells
3. `ocr_processor.py` — fallback: whole-page OCR with pytesseract → EasyOCR
4. Voter pipeline uses separate per-card OCR (PaddleOCR) with dedicated EPIC strip extraction

### Frontend Architecture

Next.js 14 App Router with a single-page multi-view pattern:
- `app/page.tsx` renders `NavigationMenu` + the active view
- **5 isolated views**: ElectionResultsView, BoothView, ConstituencyView, VotersView, ExcelMergeView (each has its own state, no shared state between views)
- Each view uses a dedicated upload hook (`useFileUpload`, `useBoothUpload`, `useVotersUpload`, `useBulkVotersUpload`)
- `lib/api.ts` — ~25 async functions for all backend endpoints with SSE stream handling
- UI: Tailwind CSS + shadcn/ui + Fortune Sheet (@fortune-sheet/react) for spreadsheet preview

### Key Backend Modules

| Module | Role |
|--------|------|
| `main.py` | All FastAPI endpoints (40+), no routers |
| `task_store.py` | In-memory task storage dicts, shared across modules |
| `pdf_processor.py` | Multi-strategy extraction orchestrator |
| `grid_ocr_processor.py` | OpenCV grid-line cell extraction for scanned tables |
| `voters_pdf_processor.py` | Per-card voter extraction pipeline |
| `excel_creator.py` / `deterministic_excel_creator.py` | AI vs deterministic Excel generation |
| `formatter.py` | Excel styling (headers, borders, widths, SUM formulas) |
| `election_processor.py` | Election-specific header standardization |
| `party_normalizer.py` | Tamil Nadu party abbreviation mapping |
| `models.py` | All Pydantic request/response models |

## Environment Variables

**Backend (`backend/.env`):**
```
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE=52428800          # 50MB (code default)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001
ANTHROPIC_API_KEY=sk-ant-...    # Primary AI (optional)
OPENAI_API_KEY=sk-proj-...      # Fallback AI (optional)
```

**Frontend (`frontend/.env.local`):**
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Excel Output Standards

- Column widths: 15-20 characters (NOT default 8.43)
- Row heights: Header 70px, data 18px
- Headers: Dark blue background (#1F4E79), white text, wrap_text=True
- Freeze panes: Header row frozen
- SUM formulas: Auto-generated for numeric columns

Validate with: `python backend/recalc.py output.xlsx`

## Common Issues

| Problem | Solution |
|---------|----------|
| Backend won't start | `./verify_setup.sh`, check venv activated, ports 8000/3000 free |
| OCR not working | Install Tesseract + Poppler, run `python backend/test_ocr_setup.py` |
| File validation errors | `brew install libmagic`, check MAX_FILE_SIZE in .env |
| Docker build fails | Ensure 4GB+ memory, check .env files configured |
| API docs | Swagger UI at http://localhost:8000/docs |
