# PDF to Excel Converter

A full-stack application that converts tabular PDFs (especially Indian election result PDFs like FORM 20) to professionally formatted Excel spreadsheets with AI-powered intelligence.

## Features

- 📄 **Multi-strategy PDF extraction**: pdfplumber → camelot → tabula fallback
- 🤖 **AI-enhanced processing**: Claude/OpenAI for intelligent document analysis
- 📊 **Professional Excel formatting**: Auto-formatted headers, formulas, and styling
- 🔄 **Multi-page table merging**: Intelligent column standardization across pages
- 🏛️ **Tamil Nadu party normalization**: Automatic party name standardization
- 🌐 **Web interface**: Modern Next.js frontend with real-time progress
- 🔍 **OCR support**: Handles scanned/image-based PDFs
- 📝 **Column filtering**: Select and customize columns in output Excel

## Quick Start

### Prerequisites

- **Python 3.8+**
- **Node.js 18+** (for frontend)
- **System dependencies** (see below)

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd "Excel Convertor copy"
```

### 2. Install System Dependencies

**macOS:**
```bash
brew install ghostscript openjdk tesseract poppler libmagic
```

**Ubuntu/Debian:**
```bash
sudo apt-get update
sudo apt-get install ghostscript default-jre tesseract-ocr poppler-utils libmagic1
```

**Windows:**
- Install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki
- Install Poppler from: https://github.com/oschwartz10612/poppler-windows/releases
- Install Java 8+ from: https://adoptium.net/

### 3. Backend Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install Python dependencies
cd backend
pip install -r requirements.txt

# Create .env file from example
cp .env.example .env
# Edit .env and add your API keys (see Configuration section)
```

### 4. Frontend Setup

```bash
cd frontend
npm install

# Create .env.local file from example
cp .env.example .env.local
# Edit .env.local if needed (defaults work for local development)
```

### 5. Run the Application

**Terminal 1 - Backend:**
```bash
cd backend
source ../.venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

Open http://localhost:3000 in your browser.

## Configuration

### Backend Environment Variables

Create `backend/.env`:

```bash
# Upload and output directories
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs

# File size limit (in bytes, default: 10MB)
MAX_FILE_SIZE=10485760

# CORS allowed origins (comma-separated)
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:3001

# AI Features (Optional but recommended)
# Get your API key from: https://console.anthropic.com/
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Optional: OpenAI as fallback
# Get your API key from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-proj-your-openai-key-here
```

### Frontend Environment Variables

Create `frontend/.env.local`:

```bash
# Backend API URL
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Usage

### Web Interface

1. Start both backend and frontend servers (see Quick Start)
2. Open http://localhost:3000
3. Upload a PDF file
4. Wait for conversion to complete
5. Download the Excel file

### API Usage

**Upload and convert:**
```bash
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your-document.pdf"
```

**Check status:**
```bash
curl http://localhost:8000/api/status/{task_id}
```

**Download Excel:**
```bash
curl -O http://localhost:8000/api/download/{task_id}
```

**Interactive API docs:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
.
├── backend/              # FastAPI backend
│   ├── app/             # Application code
│   ├── uploads/         # Temporary upload storage
│   ├── outputs/         # Generated Excel files
│   ├── requirements.txt # Python dependencies
│   └── .env            # Backend configuration
├── frontend/            # Next.js frontend
│   ├── app/            # Next.js app directory
│   ├── components/     # React components
│   ├── lib/            # Utility functions
│   ├── package.json    # Node dependencies
│   └── .env.local      # Frontend configuration
├── docker-compose.yml   # Docker setup
└── README.md           # This file
```

## Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

## Testing

```bash
# Verify system setup
./verify_setup.sh

# Test Claude AI integration
python test_claude.py

# Test convert endpoint
python test_convert_endpoint.py path/to/file.pdf

# Test deterministic parser
python test_deterministic_parser.py
```

## Documentation

- **[QUICK_START.md](QUICK_START.md)** - Quick start guide
- **[CLAUDE.md](CLAUDE.md)** - Claude AI integration guide
- **[HOW_TO_USE.md](HOW_TO_USE.md)** - End-user guide
- **[SETUP_AND_USAGE.md](SETUP_AND_USAGE.md)** - Detailed setup instructions
- **[ANTHROPIC_CONFIGURATION.md](ANTHROPIC_CONFIGURATION.md)** - AI configuration
- **[PARTY_NORMALIZATION.md](PARTY_NORMALIZATION.md)** - Party name normalization
- **[OCR_SETUP.md](backend/OCR_SETUP.md)** - OCR configuration

## Troubleshooting

### Backend fails to start
- Verify all system dependencies are installed: `./verify_setup.sh`
- Check virtual environment is activated
- Ensure ports 8000 (backend) and 3000 (frontend) are available

### OCR not working
- Install Tesseract and Poppler (see System Dependencies)
- Test OCR setup: `python backend/test_ocr_setup.py`
- See [backend/OCR_SETUP.md](backend/OCR_SETUP.md) for detailed troubleshooting

### File validation errors
- Ensure libmagic is installed
- Check MAX_FILE_SIZE in backend/.env (default 10MB)

### API key errors
- Verify ANTHROPIC_API_KEY or OPENAI_API_KEY is set in backend/.env
- Check API key format (should start with `sk-ant-` or `sk-proj-`)
- Ensure API key has sufficient credits/quota

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## License

[Add your license here]

## Support

For issues and questions:
- Check the documentation files in the root directory
- Review the troubleshooting section above
- Check backend logs: `tail -f backend/backend.log`
