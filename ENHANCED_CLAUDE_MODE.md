# Enhanced Claude Mode

## Overview

The **Enhanced Claude Mode** uses Anthropic's Claude AI for superior PDF table extraction with cell-level precision. This mode provides significantly better accuracy for complex PDFs, especially those with:

- Multi-page tables with repeating headers
- Inconsistent column alignments
- Section headers mixed with data
- Complex table structures
- Tables spanning multiple pages

## Key Features

### 1. **Intelligent Structure Analysis**
Claude AI analyzes the entire PDF structure to:
- Identify the true document title
- Detect actual column headers (not duplicate headers in data)
- Find duplicate header patterns across pages
- Identify section breaks and filter them out
- Validate column alignment

### 2. **Header Deduplication**
Automatically removes duplicate headers that appear on each page of multi-page tables:
- Compares rows against known header patterns
- Uses 70% similarity threshold for matching
- Preserves only unique data rows

### 3. **Column Standardization**
Ensures consistent column headers across all pages:
- Claude determines the "true" headers from the first page
- Applies standardized headers to all subsequent pages
- Handles variations in header naming

### 4. **Cell-Level Validation**
Validates extraction accuracy by:
- Sampling data rows from extracted tables
- Comparing against source PDF text
- Providing accuracy metrics (high/medium/low)
- Identifying alignment issues

### 5. **Quality Reporting**
Provides detailed metadata about extraction:
- Document title
- Number of tables processed
- Total rows extracted
- Structure analysis results
- Validation results

## How to Enable

Enhanced Claude Mode is **automatically enabled** when you have the `ANTHROPIC_API_KEY` configured in your `.env` file:

```env
# Backend .env file
ANTHROPIC_API_KEY=sk-ant-api03-xxxxx...
```

### Getting Your API Key

1. Go to [Anthropic Console](https://console.anthropic.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new API key
5. Copy the key and add to your `.env` file

## Performance Comparison

### Standard Mode (Without ANTHROPIC_API_KEY)
- Uses basic PDF extraction strategies
- Processes quickly but may miss structural issues
- Duplicate headers may appear in data
- Column alignment issues may occur
- Limited validation

### Enhanced Claude Mode (With ANTHROPIC_API_KEY)
- AI-powered structure analysis
- Removes ALL duplicate headers automatically
- Validates column alignment
- Cell-level accuracy verification
- Comprehensive quality reporting
- Takes more time but ensures perfect accuracy

## Processing Flow

```
1. Upload PDF
   ↓
2. Claude analyzes PDF structure
   ↓
3. Extract tables with multiple strategies
   ↓
4. Claude identifies:
   - Document title
   - True column headers
   - Duplicate header patterns
   - Section header patterns
   - Column alignment issues
   ↓
5. Remove duplicates and section headers
   ↓
6. Standardize headers across pages
   ↓
7. Validate cell accuracy (sample)
   ↓
8. Generate Excel with perfect formatting
```

## API Progress Messages

When Enhanced Mode is active, you'll see these progress messages:

- `Using Claude AI Enhanced Mode...` (5%)
- `Extracting tables from PDF...` (10%)
- `Analyzing table structure with Claude AI...` (40%)
- `Removing duplicate headers and section breaks...` (60%)
- `Standardizing column headers...` (70%)
- `Validating cell-level accuracy...` (85%)
- `Creating Excel file...` (75%)
- `Applying formatting...` (90%)
- `Conversion completed successfully` (100%)

## Example Use Case

### Problem PDF
A 20-page election results PDF with:
- Document title on page 1
- Column headers repeated on every page
- Section headers like "CONTINUED..." or "NEXT DISTRICT"
- Slightly different column spacing per page

### Standard Mode Result
- 20 tables with duplicate headers appearing as data rows
- Inconsistent column names
- Section headers mixed in data
- Requires manual cleanup

### Enhanced Claude Mode Result
- 1 merged table with clean data
- All duplicate headers removed automatically
- Consistent column names throughout
- Section headers filtered out
- Professional Excel output ready for use

## Cost Considerations

Enhanced Claude Mode uses the Anthropic API, which has usage costs:

- **Model**: Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)
- **Typical Usage Per PDF**:
  - Structure analysis: ~3,000-5,000 tokens
  - Validation: ~1,000-2,000 tokens
- **Estimated Cost**: $0.01-0.05 per PDF (depending on complexity)

For high-volume usage, monitor your API usage in the [Anthropic Console](https://console.anthropic.com/).

## Fallback Behavior

If Enhanced Claude Mode fails for any reason:
1. System logs the error
2. Automatically falls back to Standard Mode
3. Processing continues with basic extraction
4. User receives notification of fallback

## Technical Details

### Files Involved
- [enhanced_claude_processor.py](backend/app/enhanced_claude_processor.py) - Main processor
- [main.py](backend/app/main.py) - Integration with API
- [claude_processor.py](backend/app/claude_processor.py) - Basic Claude integration
- [pdf_processor.py](backend/app/pdf_processor.py) - Base extraction

### Claude AI Capabilities Used
1. **Document Understanding**: Extracts semantic meaning from PDF text
2. **Pattern Recognition**: Identifies repeating headers and sections
3. **Column Mapping**: Standardizes varying column names
4. **Quality Assessment**: Validates extraction accuracy

## Troubleshooting

### Enhanced Mode Not Activating
- Check that `ANTHROPIC_API_KEY` is set in `.env`
- Verify API key is valid (check Anthropic Console)
- Restart the backend server after adding the key
- Check logs for any API errors

### API Errors
- **Rate Limit**: Wait and retry, or upgrade API plan
- **Invalid Key**: Regenerate key in Anthropic Console
- **Network Issues**: Check internet connection

### Still Getting Duplicate Headers
- Enhanced Mode may not be activating (check logs)
- Complex PDFs may require manual review
- Report issues with sample PDF for improvements

## Future Enhancements

Planned improvements for Enhanced Mode:
- [ ] Multi-language support
- [ ] Custom column mapping rules
- [ ] Advanced section detection
- [ ] Automatic data type inference
- [ ] Smart formula generation
- [ ] Table relationship detection

## Support

For issues with Enhanced Claude Mode:
1. Check logs in backend console
2. Verify ANTHROPIC_API_KEY configuration
3. Test with standard mode first
4. Report bugs with sample PDFs (non-sensitive data)

## License & Attribution

This feature uses:
- **Anthropic Claude API** - [Anthropic](https://www.anthropic.com/)
- Subject to Anthropic's Terms of Service and Usage Policy
