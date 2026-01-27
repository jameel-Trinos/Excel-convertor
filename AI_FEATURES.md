# AI-Enhanced PDF to Excel Converter

## New AI Features

This PDF to Excel converter now includes OpenAI GPT-powered intelligent features for accurate document processing.

### Features

#### 1. Intelligent Document Heading Detection
- Automatically detects the main heading/title from PDF pages
- Uses AI to identify the document's subject from page text
- Replaces generic "Data extracted from..." with actual document title

#### 2. Column Header Standardization
- Analyzes column headers across all PDF pages
- Identifies similar columns with different names (e.g., "Item Name" = "Product" = "Description")
- Creates a unified column schema for consistent data merging
- Ensures all data is properly aligned when combining multiple pages

#### 3. Complete Data Extraction
- Extracts every line item from the PDF
- Uses intelligent mapping to preserve all data
- Handles multi-line cells and wrapped text

### Setup

#### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

New dependencies added:
- `openai>=1.12.0` - OpenAI API client
- `tiktoken>=0.5.2` - Token counting for API optimization

#### 2. Configure OpenAI API Key

Get your API key from [OpenAI Platform](https://platform.openai.com/api-keys)

**Option A: Environment Variable**
```bash
export OPENAI_API_KEY="sk-your-api-key-here"
```

**Option B: .env File**
```bash
cd backend
echo "OPENAI_API_KEY=sk-your-api-key-here" >> .env
```

**Option C: Docker Compose**
```yaml
# In docker-compose.yml
environment:
  - OPENAI_API_KEY=sk-your-api-key-here
```

#### 3. Run the Application

**Development Mode:**
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

**Docker:**
```bash
docker-compose up -d
```

### How It Works

#### Data Flow

```
PDF Upload
    ↓
1. Extract Tables (pdfplumber/camelot/tabula)
2. Extract Page Text
    ↓
3. AI Processing
   ├─→ Detect Document Heading (GPT-3.5-turbo)
   └─→ Standardize Column Headers (GPT-3.5-turbo)
    ↓
4. Excel Generation
   ├─→ Use detected heading as title
   ├─→ Merge tables with standardized columns
   └─→ Apply professional formatting
    ↓
Excel Download
```

#### AI Processing Details

**Heading Detection:**
- Analyzes first page text (up to 2000 characters)
- Identifies main heading using GPT-3.5-turbo
- Confidence scoring (0.0 - 1.0)
- Fallback to filename if detection fails

**Column Standardization:**
- Collects headers from all tables
- AI creates mapping of equivalent columns
- Example:
  ```json
  {
    "Item Name": ["Item Name", "Product", "Description"],
    "Quantity": ["Quantity", "Qty", "Amount"]
  }
  ```
- Merges data using standardized schema

### Configuration

#### AI Model Selection

Default model: `gpt-3.5-turbo` (cost-effective)

To use a different model:
```python
# In app/main.py
ai_processor = AIProcessor(model="gpt-4-turbo-preview")
```

#### Disable AI Features

AI features are automatically disabled if `OPENAI_API_KEY` is not set.

To explicitly disable:
```python
# In app/excel_creator.py
creator = ExcelCreator(ai_processor=None)
```

### Cost Estimation

- Model: GPT-3.5-turbo
- Cost per page: ~$0.002 USD
- 10-page PDF: ~$0.02 USD
- 100-page PDF: ~$0.20 USD

Costs include:
- Heading detection (1 API call per document)
- Column standardization (1 API call per document)

### Performance

**Processing Time:**
- Without AI: ~2-5 seconds per page
- With AI: ~4-8 seconds per page (+2-3 seconds for AI processing)

**Optimizations:**
- Response caching (same PDF = cached results)
- Text truncation (max 2000 chars for heading detection)
- Batch processing (single call for all headers)

### Examples

#### Input PDF Structure
```
Page 1:
  Sales Report Q1 2024

  | Item Name | Qty | Price |
  | Product A | 10  | $100  |

Page 2:
  | Product    | Amount | Unit Price |
  | Product B  | 20     | $200       |
```

#### Output Excel (Without AI)
```
Title: Data extracted from: sales_report.pdf

| Item Name | Qty | Price |  (Headers from page 1 only)
| Product A | 10  | $100  |
| Product B | 20  | $200  |  (Columns misaligned!)
```

#### Output Excel (With AI)
```
Title: Sales Report Q1 2024  ← AI-detected heading

| Item Name | Quantity | Price |  ← Standardized columns
| Product A | 10       | $100  |
| Product B | 20       | $200  |  ← Properly aligned!
```

### Troubleshooting

#### AI Features Not Working

1. **Check API Key:**
   ```bash
   echo $OPENAI_API_KEY
   ```

2. **Check Logs:**
   ```bash
   # Should see: "✓ OpenAI API key found - AI features enabled"
   # Not: "⚠ OPENAI_API_KEY not set - AI features disabled"
   ```

3. **Verify Installation:**
   ```bash
   pip list | grep openai
   # Should show: openai 1.12.0 or higher
   ```

#### API Errors

**Rate Limits:**
- OpenAI has rate limits based on your account tier
- Implement retry logic or upgrade your OpenAI plan

**Invalid API Key:**
```
OpenAI API error: Invalid authentication
```
- Verify your API key at https://platform.openai.com/api-keys
- Ensure no extra spaces in the key

**Network Issues:**
- Check internet connectivity
- Verify firewall allows OpenAI API access

### Fallback Behavior

If AI processing fails:
- ✓ System continues with standard extraction
- ✓ Uses generic title: "Data extracted from: filename.pdf"
- ✓ Uses headers from first table only
- ✓ No data loss - all rows extracted
- ⚠ Warning logged for debugging

### API Endpoints

All existing endpoints remain unchanged. AI processing is transparent:

- `POST /api/upload` - Upload PDF (AI processing starts automatically)
- `GET /api/status/{task_id}` - Check status
- `GET /api/progress/{task_id}` - Real-time progress (includes AI steps)
- `GET /api/download/{task_id}` - Download Excel

### Architecture

#### New Files
- **backend/app/ai_processor.py** - OpenAI integration
- **backend/.env.example** - Environment variable template

#### Modified Files
- **backend/app/models.py** - Added `ExtractionResult`, `AIMetadata`
- **backend/app/pdf_processor.py** - Added page text extraction
- **backend/app/excel_creator.py** - AI-powered column merging
- **backend/app/main.py** - AI integration in conversion flow
- **backend/requirements.txt** - OpenAI dependencies
- **docker-compose.yml** - OPENAI_API_KEY environment variable

### Security

- API keys stored in environment variables (not in code)
- `.env` file excluded from git (`.gitignore`)
- Use `.env.example` as template
- Response caching uses MD5 hashes (no sensitive data logged)

### Future Enhancements

Potential improvements:
- Support for GPT-4 for higher accuracy
- Data validation and anomaly detection
- Table structure analysis
- Multi-language support
- Custom column mapping rules
- Export mapping for reuse

### Support

For issues or questions:
- Check logs: `docker-compose logs -f backend`
- Review error messages in API responses
- Verify OpenAI account has credits
- Check PDF structure is tabular

### License

Same as main project license.
