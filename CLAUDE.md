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

### Backend (FastAPI/Python)
```bash
cd backend
source ../.venv/bin/activate  # Activate virtual environment
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

# Quality validation
python backend/recalc.py output.xlsx     # Validate Excel formulas
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
- **models.py** - Pydantic models (ExtractionResult, AIMetadata, TableData)
- **utils.py** - File validation and cleanup

**AI Pipeline (requires API keys):**
- **claude_processor.py** - Claude AI integration (primary)
- **enhanced_claude_processor.py** - Advanced Claude features
- **ai_processor.py** - OpenAI GPT integration (fallback)

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
- **column_filter.py** - Column filtering and cleanup

### Frontend (`frontend/`)
- **app/page.tsx** - Main upload page
- **components/** - DropZone, ProgressBar, PreviewModal, DownloadButton, ExcelPreview
- **lib/api.ts** - API client with SSE for progress updates
- **hooks/useFileUpload.ts** - Upload state management
- **types/index.ts** - TypeScript interfaces

### Processing Pipelines

**AI Pipeline** (with ANTHROPIC_API_KEY or OPENAI_API_KEY):
1. Upload PDF → extract tables with pdfplumber/camelot/tabula
2. Claude/OpenAI detects document heading and standardizes columns
3. AI-enhanced Excel with intelligent formatting

**Deterministic Pipeline** (no API keys needed):
1. Upload PDF → extract tables
2. Rule-based header detection and column standardization
3. Excel generation with fixed formatting rules

## Key API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF, returns task_id |
| `/api/convert` | POST | Direct conversion (deterministic) |
| `/api/status/{task_id}` | GET | Poll conversion status |
| `/api/progress/{task_id}` | GET | SSE stream for real-time progress |
| `/api/preview/{task_id}` | GET | First 10 rows of extracted data |
| `/api/download/{task_id}` | GET | Download generated Excel file |

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

Install on macOS: `brew install ghostscript openjdk`
Install on Ubuntu: `sudo apt-get install ghostscript default-jre`

## Excel Output Standards

Production-ready Excel files must have:
- Column widths: 15-20 characters (NOT default 8.43)
- Row heights: Header 70px, data 18px
- Headers: Dark blue background (#1F4E79), white text, wrap_text=True
- Freeze panes: Header row frozen
- SUM formulas: Auto-generated for numeric columns

Validate with: `python backend/recalc.py output.xlsx`

## Documentation References

- [EXCEL_FORMATTING_GUIDE.md](EXCEL_FORMATTING_GUIDE.md) - Critical formatting standards
- [DETERMINISTIC_PIPELINE.md](DETERMINISTIC_PIPELINE.md) - Non-AI processing details
- [PARTY_NORMALIZATION.md](PARTY_NORMALIZATION.md) - Tamil Nadu party name mapping
- [ANTHROPIC_CONFIGURATION.md](ANTHROPIC_CONFIGURATION.md) - Claude API setup
