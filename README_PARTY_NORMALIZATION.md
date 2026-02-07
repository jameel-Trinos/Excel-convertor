# PDF to Excel Converter with Party Normalization

## 🎯 Overview

This system converts election PDF documents to Excel spreadsheets with **automatic political party name normalization**. It uses Anthropic's Claude AI to extract data with perfect accuracy and intelligently standardizes party column names.

## ✨ Key Features

### 1. **Perfect PDF Extraction**
- Uses Claude AI for cell-level accuracy
- Handles multi-page tables
- Removes duplicate headers automatically
- Validates data completeness

### 2. **Intelligent Party Normalization**
- Recognizes 40+ party name variations
- Standardizes to clean abbreviations (DMK, AIADMK, BJP, etc.)
- Aggregates minor parties into "OTHERS"
- Preserves all vote data accurately

### 3. **Professional Excel Output**
- Formatted headers with colors
- Borders and alignment
- Auto-sized columns
- Freeze panes for easy scrolling

## 📊 Party Normalization Rules

### Major Parties (Kept Separate)

```
Dravida Munnetra Kazhagam                     → DMK
All India Anna Dravida Munnetra Kazhagam      → AIADMK
BHARATIYA JANATA PARTY                        → BJP
Indian National Congress                      → CONGRESS
VIDUTHALAI CHIRUTHAIGAL KATCHI               → VCK
PATTALI MAKKAL KATCHI                         → PMK
NAAM TAMILAR KATCHI                           → NTK
```

### Minor Parties (Aggregated)

```
BSP, CPI, CPM, MDMK, NMK                      → OTHERS
Independent, NOTA, Others                     → OTHERS
```

**Example:**
```
Before: | BSP: 30 | CPI: 25 | Independent: 40 | NOTA: 10 |
After:  | OTHERS: 105 |
```

## 🚀 Quick Start

### Prerequisites

1. **Python 3.8+**
2. **Anthropic API Key** ([Get one here](https://console.anthropic.com/))
3. **Required packages:**

```bash
cd backend
pip install -r requirements.txt
```

### Setup

```bash
# Clone or navigate to project
# From project root

# Set API key
export ANTHROPIC_API_KEY='sk-ant-your-api-key-here'

# Or create .env file
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

## 📖 Usage

### Method 1: Command Line (Simplest)

```bash
# Convert a PDF with party normalization
python3 convert_with_party_normalization.py input.pdf

# Specify output file
python3 convert_with_party_normalization.py input.pdf output.xlsx
```

### Method 2: Python API

```python
import asyncio
from backend.app.enhanced_claude_processor import EnhancedClaudeProcessor
from backend.app.excel_creator import ExcelCreator

async def convert_pdf(pdf_path, output_path):
    # Initialize processor
    processor = EnhancedClaudeProcessor(api_key="your-api-key")
    
    # Extract with party normalization enabled
    tables, metadata = await processor.enhanced_extract(
        pdf_path,
        apply_party_normalization=True
    )
    
    # Create Excel
    creator = ExcelCreator()
    creator.create_from_tables(
        tables,
        output_path,
        document_title=metadata.get("document_title", "")
    )

asyncio.run(convert_pdf("input.pdf", "output.xlsx"))
```

### Method 3: REST API

```bash
# Start server
cd backend
uvicorn app.main:app --reload --port 8000

# In another terminal, convert PDF
curl -X POST http://localhost:8000/convert \
  -F "file=@election_data.pdf" \
  -o output.xlsx
```

## 🧪 Testing

### Test Party Normalization Logic

```bash
cd backend
python3 demo_party_normalization.py
```

This will show:
- ✅ Basic party name normalization
- ✅ Variations and abbreviations
- ✅ Column aggregation with sample data
- ✅ Complete header normalization
- ✅ List of all standardized party names

### Run Unit Tests

```bash
cd backend
python3 test_party_normalizer.py
```

## 📁 Project Structure

```
Excel Convertor/
├── backend/
│   ├── app/
│   │   ├── party_normalizer.py          # ⭐ Party normalization logic
│   │   ├── enhanced_claude_processor.py  # ⭐ Claude AI integration
│   │   ├── excel_creator.py             # Excel formatting
│   │   ├── pdf_processor.py             # PDF extraction
│   │   └── main.py                      # FastAPI server
│   ├── demo_party_normalization.py       # ⭐ Demo script
│   └── test_party_normalizer.py         # Unit tests
├── convert_with_party_normalization.py   # ⭐ CLI conversion tool
├── PARTY_NORMALIZATION_GUIDE.md         # ⭐ Full documentation
├── QUICK_START_PARTY_NORMALIZATION.md   # ⭐ Quick start guide
└── README_PARTY_NORMALIZATION.md        # ⭐ This file
```

⭐ = New/Updated for party normalization feature

## 🔧 Configuration

### Add Custom Party Mappings

Edit `backend/app/party_normalizer.py`:

```python
PARTY_MAPPINGS = {
    "YOUR_PARTY": [
        "Full Party Name",
        "ABBREVIATION",
        "A.B.B.R.",
        "Abbreviation Votes",
    ],
    # ... rest of mappings
}
```

Or add programmatically:

```python
from backend.app.party_normalizer import PartyNormalizer

normalizer = PartyNormalizer()
normalizer.add_custom_mapping(
    party_name="CUSTOM_PARTY",
    variations=["Custom Party", "CP", "C.P."]
)
```

### Customize OTHERS Aggregation

Move parties between major and OTHERS categories by editing the `PARTY_MAPPINGS` dictionary.

## 📊 Example Output

### Input PDF
```
┌──────┬─────────────────────────────────────────────┬──────────┐
│ S.No │ Party Name                                  │ Votes    │
├──────┼─────────────────────────────────────────────┼──────────┤
│ 1    │ Dravida Munnetra Kazhagam                   │ 500      │
│ 2    │ All India Anna Dravida Munnetra Kazhagam    │ 450      │
│ 3    │ BHARATIYA JANATA PARTY                      │ 200      │
│ 4    │ Bahujan Samaj Party                         │ 30       │
│ 5    │ Communist Party of India                    │ 25       │
│ 6    │ Independent                                 │ 40       │
└──────┴─────────────────────────────────────────────┴──────────┘
```

### Output Excel
```
┌──────┬─────┬────────┬─────┬────────┬──────────────┐
│ S.No │ DMK │ AIADMK │ BJP │ OTHERS │ Total Votes  │
├──────┼─────┼────────┼─────┼────────┼──────────────┤
│ 1    │ 500 │ 450    │ 200 │ 95     │ 1245         │
└──────┴─────┴────────┴─────┴────────┴──────────────┘
```

*Note: OTHERS = BSP(30) + CPI(25) + Independent(40) = 95*

## 🎯 Use Cases

### Election Commission
- Standardize results from multiple polling stations
- Aggregate data for analysis
- Generate reports with consistent formatting

### Political Analysts
- Compare results across constituencies
- Track party performance over time
- Create charts and visualizations

### Data Scientists
- Clean election data for machine learning
- Perform statistical analysis
- Build predictive models

## 🛠️ Advanced Usage

### Batch Processing

```python
import os
import asyncio
from backend.app.enhanced_claude_processor import EnhancedClaudeProcessor
from backend.app.excel_creator import ExcelCreator

async def batch_convert(pdf_directory, output_directory):
    processor = EnhancedClaudeProcessor(api_key=os.getenv("ANTHROPIC_API_KEY"))
    creator = ExcelCreator()
    
    for pdf_file in os.listdir(pdf_directory):
        if pdf_file.endswith(".pdf"):
            pdf_path = os.path.join(pdf_directory, pdf_file)
            output_path = os.path.join(
                output_directory,
                pdf_file.replace(".pdf", "_normalized.xlsx")
            )
            
            print(f"Converting {pdf_file}...")
            tables, metadata = await processor.enhanced_extract(
                pdf_path,
                apply_party_normalization=True
            )
            
            creator.create_from_tables(tables, output_path)
            print(f"✅ Created {output_path}")

asyncio.run(batch_convert("pdfs", "output"))
```

### Custom Progress Callback

```python
def my_progress(percent, message):
    print(f"[{percent:3d}%] {message}")

tables, metadata = await processor.enhanced_extract(
    pdf_path,
    progress_callback=my_progress,
    apply_party_normalization=True
)
```

## 📝 API Reference

### Enhanced Claude Processor

```python
processor = EnhancedClaudeProcessor(api_key="sk-ant-...")

# Extract with party normalization
tables, metadata = await processor.enhanced_extract(
    pdf_path="input.pdf",
    progress_callback=None,           # Optional progress function
    apply_party_normalization=True    # Enable party normalization
)
```

### Party Normalizer

```python
normalizer = PartyNormalizer()

# Normalize single column name
result = normalizer.normalize_column_name("Dravida Munnetra Kazhagam")
# Returns: "DMK"

# Normalize header list
headers = normalizer.normalize_headers(["S.No", "DMK", "BSP", "Total"])
# Returns: ["S.No", "DMK", "OTHERS", "Total"]

# Normalize and aggregate data
norm_headers, norm_data = normalizer.normalize_and_aggregate_columns(
    headers=["S.No", "DMK", "BSP", "CPI"],
    data_rows=[["1", "500", "30", "25"]]
)
# Returns: (["S.No", "DMK", "OTHERS"], [["1", "500", 55]])
```

## ❓ FAQ

### Q: Will this work with any election PDF?
**A:** Best results with structured tables (e.g., Form 20). Claude AI adapts to various formats.

### Q: Can I add more parties to keep separate?
**A:** Yes! Edit `PARTY_MAPPINGS` in `party_normalizer.py`.

### Q: What if a party name isn't recognized?
**A:** Use `add_custom_mapping()` to add new variations.

### Q: Does this modify the original PDF?
**A:** No, the PDF is never modified. Only the Excel output is created.

### Q: How accurate is the extraction?
**A:** Claude AI provides near-perfect accuracy. Validation is built-in.

## 🐛 Troubleshooting

### Issue: "ANTHROPIC_API_KEY not configured"
**Solution:** 
```bash
export ANTHROPIC_API_KEY='sk-ant-your-key'
```

### Issue: "No tables found in PDF"
**Solution:** Ensure PDF contains clear tabular data with headers.

### Issue: Party name not normalized correctly
**Solution:** Add mapping:
```python
normalizer.add_custom_mapping("PARTY", ["Variation 1", "Variation 2"])
```

### Issue: OTHERS sum doesn't match
**Solution:** Check which parties are mapped to OTHERS in `PARTY_MAPPINGS`.

## 📚 Documentation

- **Quick Start**: `QUICK_START_PARTY_NORMALIZATION.md`
- **Full Guide**: `PARTY_NORMALIZATION_GUIDE.md`
- **API Reference**: `API_QUICK_REFERENCE.md`
- **Testing**: `TESTING_GUIDE.md`

## 🤝 Support

For issues or questions:
1. Run the demo: `python3 backend/demo_party_normalization.py`
2. Check logs: `backend/backend.log`
3. Review tests: `python3 backend/test_party_normalizer.py`

## 📄 License

Part of the PDF to Excel Converter project.

---

**Ready to get started?** See `QUICK_START_PARTY_NORMALIZATION.md`

**Need details?** See `PARTY_NORMALIZATION_GUIDE.md`







