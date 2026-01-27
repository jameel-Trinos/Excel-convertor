# 🚀 Setup and Usage - Party Normalization

## ⚡ Quick Setup (2 Minutes)

### Step 1: Verify Python Installation

```bash
python3 --version
# Should show Python 3.8 or higher
```

### Step 2: Install Dependencies

```bash
cd "/Volumes/Trinos/Learning/Excel Convertor/backend"
pip install -r requirements.txt
```

### Step 3: Set Anthropic API Key

```bash
# Option 1: Environment variable (temporary)
export ANTHROPIC_API_KEY='sk-ant-your-api-key-here'

# Option 2: .env file (permanent)
cd "/Volumes/Trinos/Learning/Excel Convertor"
echo "ANTHROPIC_API_KEY=sk-ant-your-key-here" > .env
```

**Get your API key**: https://console.anthropic.com/

### Step 4: Test Installation

```bash
cd "/Volumes/Trinos/Learning/Excel Convertor/backend"
python3 demo_party_normalization.py
```

✅ **If you see the demo output with party mappings, you're ready!**

---

## 📖 Usage Scenarios

### Scenario 1: Convert One PDF (Most Common)

```bash
cd "/Volumes/Trinos/Learning/Excel Convertor"

# Simple conversion
python3 convert_with_party_normalization.py election_data.pdf

# Output: election_data_normalized.xlsx
```

### Scenario 2: Specify Output Name

```bash
python3 convert_with_party_normalization.py input.pdf output_custom_name.xlsx
```

### Scenario 3: Batch Convert Multiple PDFs

Create a script `batch_convert.sh`:

```bash
#!/bin/bash
export ANTHROPIC_API_KEY='sk-ant-your-key'

for pdf in pdfs/*.pdf; do
    echo "Converting $pdf..."
    python3 convert_with_party_normalization.py "$pdf"
done
```

Run it:
```bash
chmod +x batch_convert.sh
./batch_convert.sh
```

### Scenario 4: Use Python API

```python
import asyncio
import os
from backend.app.enhanced_claude_processor import EnhancedClaudeProcessor
from backend.app.excel_creator import ExcelCreator

async def convert(pdf_path, output_path):
    processor = EnhancedClaudeProcessor(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    tables, metadata = await processor.enhanced_extract(
        pdf_path,
        apply_party_normalization=True
    )
    
    creator = ExcelCreator()
    creator.create_from_tables(
        tables,
        output_path,
        document_title=metadata.get("document_title", "")
    )
    
    print(f"✅ Created: {output_path}")

# Use it
asyncio.run(convert("input.pdf", "output.xlsx"))
```

### Scenario 5: REST API (Web Service)

**Start server:**
```bash
cd "/Volumes/Trinos/Learning/Excel Convertor/backend"
uvicorn app.main:app --reload --port 8000
```

**Convert PDF via API:**
```bash
curl -X POST http://localhost:8000/convert \
  -F "file=@election_data.pdf" \
  -o output.xlsx
```

**Using Python requests:**
```python
import requests

with open('election_data.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/convert',
        files={'file': f}
    )
    
with open('output.xlsx', 'wb') as f:
    f.write(response.content)
```

---

## 🎯 Real-World Example

### Input: Election PDF

```
═══════════════════════════════════════════════════════════════
                    FORM 20 - FINAL RESULT SHEET
═══════════════════════════════════════════════════════════════

Polling Station No: 001
Location: Main Street, Ward 5

+------+------------------------------------------+--------+
| S.No | Party Name                               | Votes  |
+------+------------------------------------------+--------+
| 1    | Dravida Munnetra Kazhagam                | 500    |
| 2    | All India Anna Dravida Munnetra Kazhagam | 450    |
| 3    | BHARATIYA JANATA PARTY                   | 200    |
| 4    | Indian National Congress                 | 150    |
| 5    | VIDUTHALAI CHIRUTHAIGAL KATCHI          | 100    |
| 6    | PATTALI MAKKAL KATCHI                    | 80     |
| 7    | NAAM TAMILAR KATCHI                      | 50     |
| 8    | Bahujan Samaj Party                      | 30     |
| 9    | Communist Party of India                 | 25     |
| 10   | Independent                              | 40     |
| 11   | NOTA                                     | 10     |
+------+------------------------------------------+--------+
Total Valid Votes: 1635
```

### Command

```bash
python3 convert_with_party_normalization.py election_form20.pdf
```

### Output: Excel File

**Header Row** (Blue background, white text, bold):
```
┌─────┬──────────────────┬─────┬────────┬─────┬──────────┬─────┬─────┬─────┬────────┬──────────────┐
│S.No │ Polling Station  │ DMK │ AIADMK │ BJP │ CONGRESS │ VCK │ PMK │ NTK │ OTHERS │ Total Votes  │
└─────┴──────────────────┴─────┴────────┴─────┴──────────┴─────┴─────┴─────┴────────┴──────────────┘
```

**Data Row** (Centered, bordered):
```
┌─────┬──────────────────┬─────┬────────┬─────┬──────────┬─────┬─────┬─────┬────────┬──────────────┐
│ 1   │ 001              │ 500 │ 450    │ 200 │ 150      │ 100 │ 80  │ 50  │ 105    │ 1635         │
└─────┴──────────────────┴─────┴────────┴─────┴──────────┴─────┴─────┴─────┴────────┴──────────────┘
```

**OTHERS breakdown:** BSP(30) + CPI(25) + Independent(40) + NOTA(10) = **105**

---

## 📊 What Gets Normalized

### Original PDF Columns → Excel Columns

```
❌ BEFORE                                    ✅ AFTER
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
S.No                                         S.No
Polling Station No                           Polling Station No
Dravida Munnetra Kazhagam              →     DMK
All India Anna Dravida Munnetra        →     AIADMK
BHARATIYA JANATA PARTY                 →     BJP
Indian National Congress               →     CONGRESS
VIDUTHALAI CHIRUTHAIGAL KATCHI        →     VCK
PATTALI MAKKAL KATCHI                  →     PMK
NAAM TAMILAR KATCHI                    →     NTK
Bahujan Samaj Party                    ↘
Communist Party of India               → →   OTHERS (aggregated)
Independent                            ↗
NOTA                                   ↗
Total Valid Votes                            Total Valid Votes
```

---

## ⚙️ Configuration Options

### Option 1: Add Custom Party

**Edit:** `backend/app/party_normalizer.py`

```python
PARTY_MAPPINGS = {
    # Add your custom party
    "CUSTOM": [
        "Custom Party Full Name",
        "CUSTOM",
        "C.U.S.T.O.M.",
        "Custom Party Votes",
    ],
    # ... existing mappings
}
```

### Option 2: Change OTHERS Grouping

**Move a party from OTHERS to separate column:**

```python
# Remove from OTHERS
PARTY_MAPPINGS = {
    "BSP": [  # Now separate instead of in OTHERS
        "Bahujan Samaj Party",
        "BSP",
        "B.S.P.",
    ],
    "OTHERS": [
        # BSP removed from here
        "CPI",
        "Communist Party of India",
        # ... rest
    ],
}
```

### Option 3: Disable Party Normalization

```python
tables, metadata = await processor.enhanced_extract(
    pdf_path,
    apply_party_normalization=False  # Disable normalization
)
```

---

## 🧪 Testing & Validation

### Test 1: Demo Script (No PDF needed)

```bash
cd backend
python3 demo_party_normalization.py
```

**Expected output:** Party mappings demo with 5 tests showing normalization.

### Test 2: Unit Tests

```bash
cd backend
python3 test_party_normalizer.py
```

**Expected output:** All tests pass ✅

### Test 3: Convert Sample PDF

```bash
# Create a test PDF (if you have one)
python3 convert_with_party_normalization.py test_election.pdf

# Check output
open test_election_normalized.xlsx
```

**Validate:**
- ✅ Party names are standardized (DMK, AIADMK, etc.)
- ✅ Minor parties are in OTHERS column
- ✅ Vote counts match original
- ✅ Excel is formatted professionally

---

## 📈 Performance

| PDF Size | Pages | Rows | Processing Time |
|----------|-------|------|-----------------|
| 500 KB   | 5     | 150  | ~10 seconds     |
| 2 MB     | 20    | 500  | ~30 seconds     |
| 5 MB     | 50    | 1000 | ~60 seconds     |

*Note: Times include Claude AI extraction + normalization + Excel creation*

---

## 🐛 Troubleshooting

### Error: "ANTHROPIC_API_KEY not configured"

**Solution:**
```bash
export ANTHROPIC_API_KEY='sk-ant-your-key-here'
# Or add to .env file
```

### Error: "No module named 'anthropic'"

**Solution:**
```bash
cd backend
pip install -r requirements.txt
```

### Error: "No tables found in PDF"

**Causes:**
- PDF is image-based (needs OCR)
- PDF has no clear table structure
- PDF is encrypted

**Solution:** Ensure PDF has extractable text and clear table structure.

### Error: Party name not normalized

**Solution:**
```python
# Add custom mapping
from backend.app.party_normalizer import PartyNormalizer

normalizer = PartyNormalizer()
normalizer.add_custom_mapping(
    "YOUR_PARTY",
    ["Full Name", "ABBR", "A.B.B.R."]
)
```

---

## 📚 Documentation Map

```
Start Here
    ↓
IMPLEMENTATION_COMPLETE.md ← You are here
    ↓
Choose your path:
    
    📖 Quick Start (5 min)
    → QUICK_START_PARTY_NORMALIZATION.md
    
    📖 Complete Guide (20 min)
    → PARTY_NORMALIZATION_GUIDE.md
    
    📖 API Reference
    → README_PARTY_NORMALIZATION.md
    
    🧪 Testing
    → Run: python3 backend/demo_party_normalization.py
```

---

## ✅ Checklist: Are You Ready?

- [ ] Python 3.8+ installed
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] ANTHROPIC_API_KEY set
- [ ] Demo script runs successfully
- [ ] You have a PDF to convert

**All checked?** You're ready! 🎉

```bash
python3 convert_with_party_normalization.py your_election.pdf
```

---

## 🎓 Learn More

- **Anthropic Claude**: https://www.anthropic.com/claude
- **API Documentation**: https://docs.anthropic.com/
- **Python Async**: https://docs.python.org/3/library/asyncio.html
- **OpenPyXL**: https://openpyxl.readthedocs.io/

---

**Ready?** Start with the demo:

```bash
cd backend
python3 demo_party_normalization.py
```

Then convert your first PDF:

```bash
cd ..
python3 convert_with_party_normalization.py your_file.pdf
```

**Questions?** See `PARTY_NORMALIZATION_GUIDE.md`







