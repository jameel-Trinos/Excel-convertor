# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PDF to Excel Converter - A full-stack application that converts tabular PDFs to professionally formatted Excel spreadsheets with AI-powered intelligence. Primary use case: Indian election result PDFs (FORM 20, etc.).

**Key Features:**
- Multi-strategy PDF extraction: pdfplumber → camelot → tabula fallback
- Two processing pipelines: AI-enhanced (Claude/OpenAI) and deterministic (no AI)
- Professional Excel formatting with SUM formulas
- Multi-page table merging with duplicate header removal
- Tamil Nadu political party name normalization

## Development Commands

### Initial Setup

**Python Virtual Environment:**
```bash
# Root-level virtual environment (recommended)
python3 -m venv .venv
source .venv/bin/activate

# Or backend-specific virtual environment
cd backend
python3 -m venv .venv
source .venv/bin/activate
```

**Install System Dependencies First:**
```bash
# macOS
brew install ghostscript openjdk tesseract poppler libmagic

# Ubuntu
sudo apt-get install ghostscript default-jre tesseract-ocr poppler-utils libmagic1
```

### Backend (FastAPI/Python)
```bash
cd backend
source ../.venv/bin/activate  # Or: source .venv/bin/activate (local venv)
pip install -r requirements.txt  # Install dependencies
uvicorn app.main:app --reload --port 8000  # Run dev server
```

### Frontend (Next.js/TypeScript)
```bash
cd frontend
npm install  # Install dependencies
npm run dev  # Run dev server on port 3000
npm run build  # Production build
npm run lint  # Run ESLint
```

### Testing
```bash
# From project root
python test_claude.py                    # Test Claude AI integration
python test_convert_endpoint.py          # Test /api/convert endpoint
python test_deterministic_parser.py      # Test deterministic pipeline
./verify_setup.sh                        # Verify system dependencies

# Backend-specific tests (from backend/ directory)
python test_party_normalizer.py          # Test party name normalization
python test_header_extractor.py          # Test header detection
python test_column_filter.py             # Test column filtering
python test_ocr_setup.py                 # Test OCR configuration

# Run PyTest suite
cd backend && pytest                     # Run all tests in backend/tests/
cd backend && pytest tests/test_specific.py  # Run specific test file

# Validation and demos
python backend/recalc.py output.xlsx     # Validate Excel formulas
python backend/example_validation.py     # Example validation workflow
python backend/demo_party_normalization.py  # Demo party normalization
```

### Docker
```bash
docker-compose up -d                     # Start both services
docker-compose down                      # Stop services
docker-compose logs -f backend           # View backend logs
```

## Architecture

### Backend (`backend/app/`)

**Core Processing:**
- **main.py** - FastAPI app with REST + SSE endpoints
- **pdf_processor.py** - Multi-strategy PDF extraction (pdfplumber/camelot/tabula)
- **structured_pdf_processor.py** - Structured PDF handling
- **ocr_processor.py** - OCR for scanned/image-based PDFs (Tesseract/EasyOCR)
- **models.py** - Pydantic models (ExtractionResult, AIMetadata, TableData)
- **utils.py** - File validation and cleanup
- **data_validator.py** - Data quality validation

**AI Pipeline (requires API keys):**
- **claude_processor.py** - Claude AI integration (primary)
- **enhanced_claude_processor.py** - Advanced Claude features
- **ai_processor.py** - OpenAI GPT integration (fallback)
- **ai_header_extractor.py** - AI-powered header extraction

**Deterministic Pipeline (no AI required):**
- **deterministic_parser.py** - Rule-based PDF parsing
- **deterministic_excel_creator.py** - Excel creation without AI
- **header_extractor.py** - Automatic header detection
- **header_fixer.py** - Header correction and standardization

**Excel Generation:**
- **excel_creator.py** - AI-enhanced Excel generation
- **formatter.py** - Styling (merged cells, colors, borders, column widths)
- **quality_checker.py** - Output validation

**Domain-Specific:**
- **election_processor.py** - Election document handling
- **party_normalizer.py** - Tamil Nadu party name standardization
- **party_name_fixer.py** - Advanced party name correction
- **column_filter.py** - Column filtering and cleanup (also accessible as ColumnFilterService)

### Frontend (`frontend/`)
- **app/page.tsx** - Main upload page
- **app/layout.tsx** - Root layout with metadata
- **components/** - DropZone, ProgressBar, PreviewModal, DownloadButton, ExcelPreview
- **lib/api.ts** - API client with SSE for progress updates
- **hooks/useFileUpload.ts** - Upload state management
- **types/index.ts** - TypeScript interfaces

**Key Dependencies:**
- Next.js 14.1.0 with App Router
- React 18 with TypeScript
- Tailwind CSS + shadcn/ui components
- Fortune Sheet (@fortune-sheet/react) for Excel preview
- react-dropzone for file uploads

### Processing Pipelines

**AI Pipeline** (with ANTHROPIC_API_KEY or OPENAI_API_KEY):
1. Upload PDF → extract tables with pdfplumber/camelot/tabula
2. Claude/OpenAI detects document heading and standardizes columns
3. AI-enhanced Excel with intelligent formatting

**Deterministic Pipeline** (no API keys needed):
1. Upload PDF → extract tables
2. Rule-based header detection and column standardization
3. Excel generation with fixed formatting rules

**OCR Pipeline** (for scanned/image-based PDFs):
1. Detect if PDF is image-based or text-extractable
2. If scanned: Tesseract OCR (primary) → EasyOCR (fallback)
3. Process extracted text through standard pipelines
4. Note: Requires Tesseract and Poppler system dependencies

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF, returns task_id |
| `/api/convert` | POST | Direct conversion (deterministic) |
| `/api/status/{task_id}` | GET | Poll conversion status |
| `/api/progress/{task_id}` | GET | SSE stream for real-time progress |
| `/api/preview/{task_id}` | GET | First 10 rows of extracted data |
| `/api/full-preview/{task_id}` | GET | Full extracted data preview |
| `/api/download/{task_id}` | GET | Download generated Excel file |
| `/api/filter-columns` | POST | Get available columns for filtering |
| `/api/filter-excel` | POST | Apply column filters and generate new Excel |
| `/api/download-modified/{task_id}` | POST | Download filtered Excel with selected columns |
| `/health` | GET | Health check endpoint |

## Environment Variables

**Backend (`backend/.env`):**
```bash
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_ORIGINS=http://localhost:3000
ANTHROPIC_API_KEY=sk-ant-...  # Primary AI (Claude)
OPENAI_API_KEY=sk-proj-...    # Fallback AI (optional)
```

**Frontend (`.env.local`):**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## System Dependencies

Backend requires:
- **Ghostscript** - for camelot-py PDF processing
- **Java 8+** - for tabula-py
- **Tesseract OCR** - for OCR on scanned PDFs
- **Poppler** - for pdf2image conversion
- **libmagic** - for python-magic file validation

Install on macOS:
```bash
brew install ghostscript openjdk tesseract poppler libmagic
```

Install on Ubuntu:
```bash
sudo apt-get install ghostscript default-jre tesseract-ocr poppler-utils libmagic1
```

## Excel Output Standards

Production-ready Excel files must have:
- Column widths: 15-20 characters (NOT default 8.43)
- Row heights: Header 70px, data 18px
- Headers: Dark blue background (#1F4E79), white text, wrap_text=True
- Freeze panes: Header row frozen
- SUM formulas: Auto-generated for numeric columns

Validate with: `python backend/recalc.py output.xlsx`

## Common Issues and Solutions

**Backend fails to start:**
- Verify all system dependencies are installed: `./verify_setup.sh`
- Check virtual environment is activated
- Ensure ports 8000 (backend) and 3000 (frontend) are available

**OCR not working:**
- Install Tesseract and Poppler (see System Dependencies)
- Test OCR setup: `python backend/test_ocr_setup.py`
- See [backend/OCR_SETUP.md](backend/OCR_SETUP.md) for detailed troubleshooting

**File validation errors:**
- Ensure libmagic is installed (`brew install libmagic` or `apt-get install libmagic1`)
- Check MAX_FILE_SIZE in backend/.env (default 10MB)

**Docker build fails:**
- Ensure Docker has sufficient memory (recommend 4GB+)
- Check that .env files are properly configured (see .env.example)

## Project Structure Notes

- **backend/tests/** - PyTest test suite (use `pytest` from backend/ directory)
- **backend/examples/** - Example PDFs for testing
- **backend/uploads/** - Temporary upload storage
- **backend/outputs/** - Generated Excel files
- **frontend/.next/** - Next.js build output (auto-generated)

## Documentation References

**Core Documentation:**
- [EXCEL_FORMATTING_GUIDE.md](EXCEL_FORMATTING_GUIDE.md) - Critical formatting standards
- [DETERMINISTIC_PIPELINE.md](DETERMINISTIC_PIPELINE.md) - Non-AI processing details
- [ANTHROPIC_CONFIGURATION.md](ANTHROPIC_CONFIGURATION.md) - Claude API setup

**Feature-Specific Documentation:**
- [PARTY_NORMALIZATION.md](PARTY_NORMALIZATION.md) - Tamil Nadu party name mapping
- [OCR_SETUP.md](backend/OCR_SETUP.md) - OCR configuration and troubleshooting
- [OCR_QUICK_REFERENCE.md](backend/OCR_QUICK_REFERENCE.md) - Quick OCR guide
- [COLUMN_FILTERING.md](COLUMN_FILTERING.md) - Column filter feature
- [HOW_TO_USE.md](HOW_TO_USE.md) - End-user guide
