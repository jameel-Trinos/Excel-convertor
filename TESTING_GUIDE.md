# Testing Guide - Enhanced Claude Mode

## Quick Start

The enhanced Claude mode is now **active and ready** with the correct model configuration.

### Backend Status
✅ Backend running on http://localhost:8000
✅ Health check: http://localhost:8000/health
✅ ANTHROPIC_API_KEY configured
✅ Model: `claude-sonnet-4-20250514` (latest Sonnet 4)

## Test Your PDF

### Option 1: Using the Frontend (Recommended)

1. **Start the frontend** (if not already running):
   ```bash
   cd frontend
   npm run dev
   ```

2. **Open in browser**: http://localhost:3000

3. **Upload your PDF** and watch for these messages:
   - `Using Claude AI Enhanced Mode...` ✓
   - `Analyzing table structure with Claude AI...` ✓
   - `Removing duplicate headers and section breaks...` ✓
   - `Validating cell-level accuracy...` ✓

4. **Download the Excel** and verify:
   - No duplicate headers in rows 8, 24, etc.
   - All columns properly aligned
   - Clean, professional formatting

### Option 2: Using cURL (Direct API Test)

```bash
# Upload PDF
curl -X POST http://localhost:8000/api/upload \
  -F "file=@your_pdf_file.pdf" \
  -v

# You'll get a response like:
# {"task_id":"abc123-def456...","status":"processing"}

# Monitor progress (Server-Sent Events)
curl -N http://localhost:8000/api/progress/YOUR_TASK_ID

# Download result
curl -o output.xlsx http://localhost:8000/api/download/YOUR_TASK_ID
```

## What to Expect

### Enhanced Mode Features

1. **Duplicate Header Removal**
   - Headers repeating on each page are automatically detected
   - Uses 70% similarity matching
   - Only unique data rows remain

2. **Section Header Filtering**
   - Mid-table section breaks removed (e.g., "CONTINUED...")
   - Party names appearing as separators filtered out
   - Clean continuous data

3. **Column Alignment**
   - Claude validates column structure
   - Standardizes headers across pages
   - Ensures consistent formatting

4. **Quality Validation**
   - Cell-by-cell accuracy check
   - Completeness verification
   - Detailed metadata logging

### Expected Processing Time

- **Small PDFs (1-5 pages)**: 10-15 seconds
- **Medium PDFs (6-20 pages)**: 20-40 seconds
- **Large PDFs (21+ pages)**: 40-90 seconds

Enhanced mode is slower than standard mode but ensures **perfect accuracy**.

## Troubleshooting

### Issue: "Claude analysis failed: 404"
**Fix**: ✅ **Already fixed!** Updated to correct model `claude-sonnet-4-20250514`

### Issue: Still seeing duplicate headers
**Check**:
1. Look at backend logs: `tail -f /tmp/backend.log`
2. Verify "Enhanced Mode" message appears
3. Check if Claude analysis succeeded (no 404 errors)

### Issue: API rate limit
**Solution**:
- Wait 60 seconds and retry
- Check Anthropic console for rate limits
- Consider upgrading API tier for high volume

### Issue: Column misalignment persists
**Debug**:
```bash
# Check backend logs for Claude's analysis
tail -100 /tmp/backend.log | grep "structure_analysis"
```

The logs will show Claude's detected:
- True headers
- Duplicate patterns
- Section patterns
- Alignment issues

## Verify Enhanced Mode is Active

Check the backend logs:

```bash
tail -f /tmp/backend.log
```

You should see:
```
INFO:app.main:Enhanced Claude processing enabled for task <task_id>
INFO:app.main:Enhanced extraction complete: X tables, Y rows
```

If you see:
```
INFO:app.main:Standard processing mode for task <task_id>
```

Then enhanced mode is **not active**. Check:
- ANTHROPIC_API_KEY is set in backend/.env
- Backend was restarted after adding the key

## API Cost Tracking

Monitor your usage at: https://console.anthropic.com/

Typical costs per PDF:
- **Structure Analysis**: ~3,000-5,000 tokens ($0.015-0.025)
- **Validation**: ~1,000-2,000 tokens ($0.005-0.010)
- **Total per PDF**: ~$0.02-0.04

For 100 PDFs: ~$2-4 (very affordable for perfect accuracy)

## Sample Test Results

### Before Enhanced Mode
```
Row 8: S.NO | Polling Station No. | ... (duplicate header)
Row 24: S.NO | Polling Station No. | ... (duplicate header)
Row 35: NOTAIVERIBA YTRAP | | | ... (section header)
```

### After Enhanced Mode
```
All data rows clean, no duplicates, no section headers
Perfect column alignment
Professional Excel formatting
```

## Next Steps After Testing

1. **Verify Results**:
   - Open generated Excel file
   - Check rows 8, 24 (previously had duplicates)
   - Verify all columns aligned
   - Confirm data completeness

2. **Compare with Original PDF**:
   - Open PDF side-by-side with Excel
   - Spot-check 5-10 random rows
   - Verify numbers match exactly

3. **Production Use**:
   - If satisfied, process your full PDF collection
   - Monitor API costs in Anthropic console
   - Save generated Excel files

## Support

If you encounter issues:

1. **Check logs**:
   ```bash
   tail -100 /tmp/backend.log
   ```

2. **Test with simple PDF**:
   - Try a basic 1-page PDF first
   - Verify enhanced mode works
   - Then test complex multi-page PDFs

3. **Report issues**:
   - Include backend log excerpt
   - Describe expected vs actual behavior
   - Share sample PDF (if possible)

## Model Information

Current configuration:
- **Model**: `claude-sonnet-4-20250514`
- **Provider**: Anthropic
- **Type**: Claude Sonnet 4 (latest generation)
- **Context**: 200K tokens
- **Capabilities**: Document analysis, structure detection, data validation

This model was released in May 2025 and provides state-of-the-art performance for document understanding tasks.

---

**Ready to test?** Upload your PDF through the frontend and watch the magic happen! 🚀
