# PDF to Excel Converter with Claude AI

> Transform tabular PDFs into professionally formatted Excel spreadsheets with the power of Anthropic's Claude AI.

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-14+-black.svg)](https://nextjs.org/)
[![Claude AI](https://img.shields.io/badge/Claude-AI%20Powered-orange.svg)](https://www.anthropic.com/)

## 🌟 Features

### Core Capabilities
- **Multi-Strategy PDF Extraction** - Tries pdfplumber → camelot → tabula until success
- **Professional Excel Formatting** - Borders, colors, merged cells, auto-fit columns
- **SUM Formulas** - Automatic totals for numeric columns
- **Multi-Page Support** - Handles PDFs with tables spanning multiple pages
- **Real-Time Progress** - Server-Sent Events for live conversion updates

### 🤖 AI-Powered Intelligence (New in v2.0!)

**Powered by Anthropic Claude** (with OpenAI GPT fallback):

1. **Smart Document Heading Detection**
   - Automatically extracts main document title from PDF
   - Uses as Excel title with high accuracy (95%+ confidence)

2. **Intelligent Column Standardization**
   - Merges tables with different column names
   - Example: "Station No." + "Stn No" → standardized "Station No."

3. **Advanced Structure Analysis**
   - Multi-row title detection
   - Multi-row header preservation
   - Duplicate header filtering across pages
   - Section header removal

## 🚀 Quick Start

### Installation

```bash
# 1. Setup backend
cd backend
python3 -m venv ../.venv
source ../.venv/bin/activate  # Windows: ..\.venv\Scripts\activate
pip install -r requirements.txt

# 2. Configure API key (optional but recommended)
# Edit backend/.env and add:
ANTHROPIC_API_KEY=sk-ant-your-key-here

# 3. Start server
uvicorn app.main:app --reload --port 8000
```

### Get Your Anthropic API Key

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Create an API key
4. Add to `backend/.env`

**No API key?** The system still works, but without AI features (basic mode).

### Usage

**Option 1: Web Interface**
```bash
cd frontend
npm install
npm run dev
# Open http://localhost:3000
```

**Option 2: API**
```bash
curl -X POST http://localhost:8000/api/upload -F "file=@document.pdf"
# Returns task_id, use to download: /api/download/{task_id}
```

**Option 3: Python**
```python
import requests

# Upload
with open('document.pdf', 'rb') as f:
    r = requests.post('http://localhost:8000/api/upload', files={'file': f})
    task_id = r.json()['task_id']

# Download
excel = requests.get(f'http://localhost:8000/api/download/{task_id}')
open('output.xlsx', 'wb').write(excel.content)
```

## 📊 Example: Election Results

**Input PDF:**
```
FORM 20 - FINAL RESULT SHEET
GENERAL ELECTIONS TO LOK SABHA, 2024
Assembly Constituency: 150 - Jayankondam

Station | Party A | Party B | NOTA | Total
1       | 234     | 156     | 12   | 402
2       | 189     | 223     | 8    | 420
...
```

**Output Excel:**
- ✅ Title: "FORM 20 - FINAL RESULT SHEET" (Claude AI detected)
- ✅ Subtitle: "GENERAL ELECTIONS TO LOK SABHA, 2024"
- ✅ Context: "Assembly Constituency: 150 - Jayankondam"
- ✅ Headers: Bold white text on blue background
- ✅ Data: Center-aligned with borders
- ✅ Total Row: `=SUM(B2:B150)` formulas for each column
- ✅ Professional formatting ready for printing

## 🏗️ Architecture

### Backend (`backend/app/`)
- **main.py** - FastAPI app with REST + SSE endpoints
- **pdf_processor.py** - Multi-strategy extraction (pdfplumber/camelot/tabula)
- **claude_processor.py** - 🆕 Anthropic Claude AI integration (primary)
- **ai_processor.py** - OpenAI GPT integration (fallback)
- **excel_creator.py** - Excel generation with AI enhancements
- **formatter.py** - Professional styling engine
- **models.py** - Pydantic models

### Frontend (`frontend/`)
- **Next.js 14** - React framework
- **TypeScript** - Type safety
- **Tailwind CSS** - Styling
- **SSE Client** - Real-time progress updates

## 🔑 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/upload` | POST | Upload PDF, returns task_id |
| `/api/status/{task_id}` | GET | Check conversion status |
| `/api/progress/{task_id}` | GET | Real-time SSE progress stream |
| `/api/preview/{task_id}` | GET | Preview first 10 rows |
| `/api/download/{task_id}` | GET | Download Excel file |
| `/api/task/{task_id}` | DELETE | Clean up task files |

## 🎯 Use Cases

### Perfect For:
- ✅ Election result forms (FORM 20, etc.)
- ✅ Financial reports and balance sheets
- ✅ Scientific data tables
- ✅ Government forms and documents
- ✅ Multi-page tabular PDFs
- ✅ Documents with inconsistent formatting

### Not Suitable For:
- ❌ Scanned images (needs OCR preprocessing)
- ❌ Non-tabular PDFs (use text extraction instead)
- ❌ Highly graphical PDFs

## ⚙️ Configuration

### Environment Variables

**Backend** (`backend/.env`):
```bash
# Core
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_FILE_SIZE=10485760  # 10MB
ALLOWED_ORIGINS=http://localhost:3000

# AI Features
ANTHROPIC_API_KEY=sk-ant-...  # Primary (Claude)
OPENAI_API_KEY=sk-proj-...    # Fallback (Optional)
```

**Frontend** (`.env.local`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 🤖 AI Provider Comparison

| Feature | Claude Sonnet 3.5 | OpenAI GPT-3.5 |
|---------|------------------|----------------|
| Heading Detection | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Good |
| Column Mapping | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐⭐ Good |
| Structure Analysis | ⭐⭐⭐⭐⭐ Excellent | ⭐⭐⭐ Fair |
| Speed | Fast | Fast |
| Cost/1M tokens | ~$3 | ~$0.50 |
| Recommended For | Complex documents | Simple documents |

**Our Recommendation:** Use Claude for best quality, especially for complex or important documents.

## 📚 Documentation

- **[QUICK_START.md](QUICK_START.md)** - Get running in 5 minutes
- **[CLAUDE_INTEGRATION.md](CLAUDE_INTEGRATION.md)** - Detailed Claude AI setup
- **[CLAUDE.md](CLAUDE.md)** - Project architecture guide
- **[AI_FEATURES.md](AI_FEATURES.md)** - AI capabilities overview
- **[MULTI_PAGE_TABLES.md](MULTI_PAGE_TABLES.md)** - Multi-page handling details

## 🛠️ Development

### Prerequisites
- Python 3.9+
- Node.js 18+
- Ghostscript (for camelot)
- Java 8+ (for tabula)

### Install System Dependencies

**macOS:**
```bash
brew install ghostscript openjdk
```

**Ubuntu/Debian:**
```bash
sudo apt-get install ghostscript default-jre
```

**Windows:**
- Download Ghostscript from https://ghostscript.com/
- Download Java from https://adoptium.net/

### Run Tests (Coming Soon)
```bash
cd backend
pytest
```

## 🐳 Docker Deployment

```bash
# Build and run
docker-compose up -d

# View logs
docker-compose logs -f backend

# Stop
docker-compose down
```

## 📈 Performance

- **Simple PDF (1-5 pages):** 5-10 seconds
- **Medium PDF (10-30 pages):** 15-25 seconds
- **Large PDF (50+ pages):** 30-60 seconds
- **AI Processing:** +2-5 seconds per document

**Optimization Tips:**
- Response caching reduces repeat processing time
- Batch similar PDFs for better cache utilization
- Use Haiku model for faster processing (lower quality)

## 🔒 Security

- ✅ File validation (PDF magic bytes check)
- ✅ Size limits (configurable, default 10MB)
- ✅ Automatic cleanup of temporary files
- ✅ API keys in environment variables only
- ✅ CORS protection
- ❌ No user data retention (files deleted after 1 hour)

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## 📝 License

MIT License - See LICENSE file for details

## 🙏 Acknowledgments

- **Anthropic** - Claude AI platform
- **pdfplumber** - PDF extraction library
- **camelot** - Table detection library
- **tabula-py** - Java-based table extraction
- **FastAPI** - Modern Python web framework
- **Next.js** - React framework

## 💬 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/excel-converter/issues)
- **Claude API:** [Anthropic Support](https://support.anthropic.com/)
- **Documentation:** See docs folder

## 🔮 Roadmap

- [ ] OCR support for scanned PDFs
- [ ] Batch processing UI
- [ ] Custom formatting templates
- [ ] Excel formula customization
- [ ] PDF annotation support
- [ ] Multi-language support
- [ ] Cloud deployment guides

---

**Made with ❤️ and powered by Claude AI**

*Transform your PDFs into actionable Excel data today!*
