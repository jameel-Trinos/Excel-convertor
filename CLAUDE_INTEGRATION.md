# Claude (Anthropic) Integration Guide

This document explains how the PDF to Excel Converter uses Anthropic's Claude AI for intelligent document processing.

## Overview

The application now supports **two AI providers** for enhanced PDF processing:

1. **Anthropic Claude** (Primary, Recommended)
2. **OpenAI GPT** (Fallback, Legacy)

Claude is the **preferred AI provider** due to its superior performance in document analysis, text extraction, and structured data processing.

## Features Powered by Claude AI

### 1. Document Heading Detection
Claude analyzes the first page of your PDF to intelligently extract the main document title or heading, which is then used as the Excel file title.

**Example:**
- Input PDF: Election results form with title "FORM 20 - GENERAL ELECTIONS 2024"
- Claude extracts: "FORM 20 - GENERAL ELECTIONS 2024"
- Excel file uses this as the title row

### 2. Column Header Standardization
When PDFs span multiple pages with slightly different column headers, Claude intelligently maps them to a standardized schema.

**Example:**
```
Page 1 headers: ["Station No.", "Party A", "Party B", "NOTA", "Total"]
Page 2 headers: ["Stn No", "Party A", "Party B", "None of Above", "Total Votes"]

Claude creates mapping:
{
  "Station No.": ["Station No.", "Stn No"],
  "Party A": ["Party A", "Party A"],
  "Party B": ["Party B", "Party B"],
  "NOTA": ["NOTA", "None of Above"],
  "Total": ["Total", "Total Votes"]
}
```

### 3. Table Structure Analysis (Advanced)
Claude can analyze complex table structures to identify:
- Title rows (merged cells, document headers)
- Multi-row column headers
- Section headers within tables
- Data start positions

## Setup Instructions

### Step 1: Get Your Anthropic API Key

1. Visit [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in to your account
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key (starts with `sk-ant-`)

### Step 2: Configure Environment Variables

Edit the `.env` file in the `backend` directory:

```bash
# AI Features (Anthropic Claude - Primary)
ANTHROPIC_API_KEY=sk-ant-your-api-key-here

# Optional: OpenAI as fallback (if Claude fails)
# OPENAI_API_KEY=sk-proj-your-openai-key-here
```

### Step 3: Install Dependencies

```bash
cd backend
source ../.venv/bin/activate
pip install -r requirements.txt
```

This will install the Anthropic SDK (`anthropic>=0.18.0`).

### Step 4: Start the Backend

```bash
uvicorn app.main:app --reload --port 8000
```

You should see in the logs:
```
✓ Anthropic Claude API key found - Claude AI features enabled (Primary)
```

## Usage

### Via Web Interface

1. Start the frontend: `cd frontend && npm run dev`
2. Open http://localhost:3000
3. Upload a PDF file
4. The system will automatically use Claude for AI processing
5. Monitor progress - you'll see "Claude AI: Detecting document heading..." in real-time

### Via API

```bash
# Upload PDF
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your-document.pdf"

# Response
{
  "task_id": "abc-123-def",
  "filename": "your-document.pdf",
  "size": 524288,
  "message": "File uploaded successfully. Conversion started."
}

# Monitor progress (Server-Sent Events)
curl http://localhost:8000/api/progress/abc-123-def

# Download Excel
curl -O http://localhost:8000/api/download/abc-123-def
```

## AI Provider Fallback Logic

The system uses this priority order:

1. **Try Claude (Anthropic)** - If `ANTHROPIC_API_KEY` is set
2. **Fallback to OpenAI** - If Claude unavailable but `OPENAI_API_KEY` is set
3. **No AI Features** - If neither key is set (basic extraction only)

This ensures maximum reliability while preferring the superior Claude model.

## Model Selection

### Default Models

- **Claude**: `claude-3-5-sonnet-20241022` (Sonnet 3.5 - excellent balance of quality and speed)
- **OpenAI**: `gpt-3.5-turbo` (fast and cost-effective)

### Customizing the Claude Model

Edit `backend/app/claude_processor.py`:

```python
class ClaudeProcessor:
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-opus-20240229"):
        # Use Opus for maximum quality (slower, more expensive)
        # Use Sonnet for balanced quality/speed (recommended)
        # Use Haiku for speed (faster, less detailed)
```

Available models:
- `claude-3-opus-20240229` - Highest intelligence
- `claude-3-5-sonnet-20241022` - Best balance (default)
- `claude-3-haiku-20240307` - Fastest, most economical

## Performance Comparison

| Feature | Claude Sonnet 3.5 | OpenAI GPT-3.5 |
|---------|------------------|----------------|
| Heading Extraction | Excellent | Good |
| Column Mapping | Excellent | Good |
| Structure Analysis | Excellent | Fair |
| Speed | Fast | Fast |
| Cost per 1M tokens | ~$3 | ~$0.50 |
| Reliability | Very High | High |

## Troubleshooting

### "AI features disabled" message

**Problem:** You see `⚠ No AI API keys set - AI features disabled`

**Solution:**
1. Check that `ANTHROPIC_API_KEY` is set in `.env`
2. Restart the backend server
3. Verify the key starts with `sk-ant-`

### Claude API errors

**Problem:** Claude requests fail with authentication errors

**Solutions:**
1. Verify your API key is valid
2. Check your Anthropic account has credits
3. Ensure you're using a supported model name
4. Check Anthropic's [status page](https://status.anthropic.com/)

### Fallback to OpenAI

**Problem:** System uses OpenAI instead of Claude

**Solution:**
1. Check `ANTHROPIC_API_KEY` is correctly set (no typos)
2. Review backend logs for Claude initialization errors
3. Ensure the `anthropic` package is installed: `pip show anthropic`

## Advanced: Custom Claude Integration

You can extend the `ClaudeProcessor` class for custom behavior:

```python
# backend/app/claude_processor.py

def extract_metadata(self, page_texts: List[str]) -> Dict[str, any]:
    """Extract custom metadata using Claude."""
    prompt = """Analyze this document and extract:
    - Document type (form, report, invoice, etc.)
    - Date mentioned (if any)
    - Key entities (names, organizations)

    Return JSON format."""

    message = self.client.messages.create(
        model=self.model,
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )

    return json.loads(message.content[0].text)
```

## Cost Optimization

### Tips to Reduce API Costs

1. **Cache responses** - Already implemented in `ClaudeProcessor._response_cache`
2. **Limit page text** - Only first 2000 chars sent for heading detection
3. **Use Haiku for simple tasks** - Switch to `claude-3-haiku-20240307` for basic extraction
4. **Batch processing** - Process multiple PDFs in one session to maximize cache usage

### Estimated Costs

For a typical 10-page election results PDF:
- Heading detection: ~500 tokens = $0.0015
- Column standardization: ~1000 tokens = $0.003
- **Total per PDF: ~$0.005** (half a cent)

## Security Best Practices

1. **Never commit API keys** - Always use `.env` files (already in `.gitignore`)
2. **Rotate keys regularly** - Generate new keys every 90 days
3. **Use environment-specific keys** - Different keys for dev/staging/production
4. **Monitor usage** - Check Anthropic console for unexpected spikes
5. **Set spending limits** - Configure budget alerts in Anthropic dashboard

## Comparison: Claude vs OpenAI

### When to Use Claude (Recommended)
- Complex document structures
- Multi-page table analysis
- High-accuracy requirements
- Documents with inconsistent formatting
- Election forms, legal documents, financial reports

### When to Use OpenAI (Fallback)
- Simple single-page tables
- Cost is primary concern
- Legacy integrations
- Simpler document types

## Support

For issues related to:
- **Claude API**: [Anthropic Support](https://support.anthropic.com/)
- **This integration**: Create an issue in the project repository
- **General PDF processing**: Check project documentation

## Changelog

### v2.0.0 - Claude Integration
- Added Anthropic Claude as primary AI provider
- Implemented intelligent fallback to OpenAI
- Enhanced column mapping with Claude
- Improved heading detection accuracy
- Added AI provider tracking in metadata

### v1.0.0 - Initial Release
- OpenAI GPT integration only
