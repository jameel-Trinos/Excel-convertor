# Quick Start: Party Normalization

## 🚀 Get Started in 3 Steps

### Step 1: Set Up API Key

```bash
# Set your Anthropic API key
export ANTHROPIC_API_KEY='sk-ant-your-api-key-here'

# Or add to .env file in the project root
echo "ANTHROPIC_API_KEY=sk-ant-your-api-key-here" > .env
```

### Step 2: Test the Feature

Run the demo to see party normalization in action:

```bash
cd backend
python3 demo_party_normalization.py
```

You should see output like:

```
╔==============================================================================╗
║                    PARTY NAME NORMALIZER - DEMO                              ║
╚==============================================================================╝

================================================================================
DEMO 1: BASIC PARTY NAME NORMALIZATION
================================================================================

Input Column Name                              →  Normalized Name
--------------------------------------------------------------------------------
Dravida Munnetra Kazhagam                      →  DMK
All India Anna Dravida Munnetra Kazhagam       →  AIADMK
BHARATIYA JANATA PARTY                         →  BJP
Indian National Congress                       →  CONGRESS
...
```

### Step 3: Convert Your PDF

```bash
# From project root
python3 convert_with_party_normalization.py your_election_data.pdf
```

## 📊 What You Get

### Before Normalization

Your PDF might have columns like:
- `Dravida Munnetra Kazhagam`
- `All India Anna Dravida Munnetra Kazhagam`
- `BHARATIYA JANATA PARTY`
- `Bahujan Samaj Party`
- `Communist Party of India`
- `Independent`
- `NOTA`

### After Normalization

Clean, standardized Excel with:
- `DMK`
- `AIADMK`
- `BJP`
- `CONGRESS`
- `VCK`
- `PMK`
- `NTK`
- `OTHERS` (BSP + CPI + Independent + NOTA + etc.)

## 🎯 Key Features

✅ **Automatic Party Detection**: Recognizes 40+ party name variations  
✅ **Smart Aggregation**: Combines minor parties into OTHERS  
✅ **Data Preservation**: All vote counts are accurately maintained  
✅ **AI-Powered**: Uses Claude AI for perfect PDF extraction

## 📝 Example Usage

```bash
# Convert a single PDF
python3 convert_with_party_normalization.py election_form20.pdf

# Specify custom output name
python3 convert_with_party_normalization.py input.pdf output_normalized.xlsx
```

### Expected Output:

```
================================================================================
PDF TO EXCEL CONVERTER WITH PARTY NORMALIZATION
================================================================================
Input PDF: election_form20.pdf
Output Excel: election_form20_normalized.xlsx

📄 Step 1: Extracting data from PDF using Claude AI...
--------------------------------------------------------------------------------
   [ 10%] Extracting tables from PDF...
   [ 40%] Analyzing table structure with Claude AI...
   [ 60%] Removing duplicate headers and section breaks...
   [ 70%] Standardizing column headers...
   [ 75%] Normalizing political party columns...
   [ 85%] Validating cell-level accuracy...
   [ 95%] Enhanced extraction complete
✅ Extracted 1 table(s) with 150 total rows

🎯 Step 2: Party Column Normalization Applied
--------------------------------------------------------------------------------
Final normalized headers (11 columns):
   1. S.No.
   2. Polling Station No
   3. DMK
   4. AIADMK
   5. BJP
   6. CONGRESS
   7. VCK
   8. PMK
   9. NTK
   10. OTHERS
   11. Total Valid Votes

✅ Party normalization complete:
   • Final columns: 11
   • Total rows: 150

📊 Step 3: Creating Excel file...
--------------------------------------------------------------------------------
✅ Excel file created successfully: election_form20_normalized.xlsx
   • File size: 45,623 bytes (44.6 KB)

================================================================================
✅ CONVERSION COMPLETE
================================================================================

Party Normalization Summary:
  • DMK columns → DMK
  • AIADMK columns → AIADMK
  • BJP columns → BJP
  • Congress columns → CONGRESS
  • VCK columns → VCK
  • PMK columns → PMK
  • NTK columns → NTK
  • All other parties → OTHERS (aggregated)

📂 Output file: election_form20_normalized.xlsx
```

## 🔧 Using with Python API

```python
import asyncio
import os
from backend.app.enhanced_claude_processor import EnhancedClaudeProcessor
from backend.app.excel_creator import ExcelCreator

async def convert_pdf(pdf_path, output_path):
    # Initialize processor with API key
    processor = EnhancedClaudeProcessor(
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Extract with party normalization
    tables, metadata = await processor.enhanced_extract(
        pdf_path,
        apply_party_normalization=True
    )
    
    # Create Excel
    creator = ExcelCreator()
    creator.create_from_tables(
        tables,
        output_path,
        source_filename=pdf_path,
        document_title=metadata.get("document_title", "")
    )
    
    print(f"✅ Done! Created {output_path}")

# Run
asyncio.run(convert_pdf("input.pdf", "output.xlsx"))
```

## 🌐 Using with REST API

### Start the Server

```bash
cd backend
uvicorn app.main:app --reload
```

### Convert a PDF

```bash
curl -X POST http://localhost:8000/convert \
  -F "file=@election_data.pdf" \
  -H "Content-Type: multipart/form-data" \
  -o output.xlsx
```

The party normalization is automatically applied!

## 📚 Party Mapping Reference

| Input | Output |
|-------|--------|
| Dravida Munnetra Kazhagam | DMK |
| All India Anna Dravida Munnetra Kazhagam | AIADMK |
| BHARATIYA JANATA PARTY | BJP |
| Indian National Congress | CONGRESS |
| VIDUTHALAI CHIRUTHAIGAL KATCHI | VCK |
| PATTALI MAKKAL KATCHI | PMK |
| NAAM TAMILAR KATCHI | NTK |
| BSP, CPI, CPM, Independent, NOTA, Others | OTHERS |

## ❓ Troubleshooting

### "ANTHROPIC_API_KEY not configured"

**Solution**: Set the environment variable:
```bash
export ANTHROPIC_API_KEY='sk-ant-your-key-here'
```

### "No tables found in PDF"

**Solution**: Make sure your PDF contains tabular data with clear column headers.

### "Party name not recognized"

**Solution**: Add custom mappings in `backend/app/party_normalizer.py`:
```python
normalizer.add_custom_mapping("YOUR_PARTY", ["Variation 1", "Variation 2"])
```

## 📖 More Information

- Full documentation: `PARTY_NORMALIZATION_GUIDE.md`
- API reference: `API_QUICK_REFERENCE.md`
- Testing guide: `TESTING_GUIDE.md`

## 💡 Tips

1. **Preserve Original**: The original PDF is never modified
2. **Check Output**: Review the Excel file to verify normalization
3. **Custom Parties**: Add regional parties using `add_custom_mapping()`
4. **Batch Processing**: Use a loop to process multiple PDFs
5. **Validation**: Check that OTHERS sums match expected totals

## 🎉 Success!

You're now ready to convert election PDFs with automatic party name normalization!

For questions or issues, see the full guide: `PARTY_NORMALIZATION_GUIDE.md`







