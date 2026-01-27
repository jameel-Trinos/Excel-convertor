# Comprehensive Data Validation System

## Overview

The validation system provides multi-layered validation to catch extraction errors before Excel creation. It's specifically designed for Indian Election Form 20 documents but can be adapted for similar tabular PDFs.

## Architecture

The validation system consists of four main components:

### 1. StructureValidator
Validates Form 20 structure requirements:
- ✅ First column is "Polling Station No." or similar
- ✅ Has expected candidate columns (14-15 columns)
- ✅ Has NOTA column
- ✅ Has reasonable row count (50-300 polling stations)

### 2. DataTypeValidator
Validates numeric columns (vote counts):
- ✅ All values are numeric or empty
- ✅ Flags negative numbers
- ✅ Flags unreasonably large numbers (>10000)
- ✅ Detects OCR errors: "O" instead of "0", "l" instead of "1"

### 3. ConsistencyValidator
Validates data consistency:
- ✅ All rows have same column count as headers
- ✅ Sequential polling station numbers (with allowed gaps)
- ✅ Total row matches sum of columns (if present)
- ✅ No duplicate polling stations

### 4. QualityScorer
Calculates overall confidence score (0.0-1.0) based on:
- Extraction method (OCR lower than pdfplumber)
- Validation pass rate
- Empty cell ratio
- Data type consistency

## Integration

The validation is integrated into the conversion flow in `process_conversion()`:

```python
# After extraction, before Excel creation
validator = ExtractionValidator()
validation_result = validator.validate(extraction_result.tables, extraction_method)

if validation_result.confidence < 0.7:
    # Mark task for manual review
    task.status = "needs_review"
    task.validation_issues = validation_result.to_dict()
    return
```

## ValidationResult Format

The `ValidationResult` dataclass matches the user specification:

```python
@dataclass
class ValidationResult:
    passed: bool
    confidence: float  # 0.0 to 1.0
    issues: List[str]  # Human-readable issue descriptions
    warnings: List[str]  # Non-critical issues
    suggestions: List[str]  # Suggested fixes
```

## Usage Example

```python
from app.data_validator import ExtractionValidator
from app.models import TableData

# Create validator
validator = ExtractionValidator()

# Validate extracted tables
validation_result = validator.validate(tables, extraction_method="pdfplumber")

# Check results
if validation_result.confidence < 0.7:
    print("Low confidence - manual review needed")
    print(f"Issues: {validation_result.issues}")
    print(f"Warnings: {validation_result.warnings}")
    print(f"Suggestions: {validation_result.suggestions}")
```

## Individual Validators

You can also use individual validators for specific checks:

```python
from app.data_validator import StructureValidator, DataTypeValidator, ConsistencyValidator

structure_validator = StructureValidator()
structure_result = structure_validator.validate_form20_structure(table)

data_type_validator = DataTypeValidator()
data_type_result = data_type_validator.validate_numeric_columns(table)

consistency_validator = ConsistencyValidator()
consistency_result = consistency_validator.validate_consistency(table)
```

## Task Status

Tasks can now have a `needs_review` status when validation confidence is below 0.7:

- **Status**: `needs_review`
- **Progress**: 85% (stops before Excel creation)
- **Message**: Includes confidence score and recommendation
- **validation_issues**: Contains full validation result as dictionary

## API Response

The status endpoint now includes validation issues:

```json
{
  "task_id": "abc123",
  "status": "needs_review",
  "progress": 85,
  "message": "Extraction completed but validation confidence is low (65.0%). Manual review recommended.",
  "validation_issues": {
    "passed": false,
    "confidence": 0.65,
    "issues": ["Non-numeric value 'O' in column 'Candidate 1'", ...],
    "warnings": ["Large gap in station numbers: 5 to 10 (gap of 5)", ...],
    "suggestions": ["Review numeric columns for extraction errors", ...]
  }
}
```

## Configuration

### Form 20 Expectations

The validators use these default expectations (can be customized):

- **Column Count Range**: 14-20 columns
- **Row Count Range**: 50-300 polling stations
- **Max Vote Count**: 10,000 (flags larger as suspicious)
- **Min Vote Count**: 0 (flags negative as error)

### OCR Error Detection

The system detects common OCR errors:
- Letter 'O' instead of zero
- Letter 'l' or 'I' instead of one
- Mixed letter/digit patterns

## Confidence Scoring

The overall confidence score is calculated as:

```
confidence = (
    base_confidence * 0.4 +          # Extraction method
    avg_validation_confidence * 0.4 + # Validation results
    type_consistency * 0.2            # Data type consistency
) * (1 - empty_penalty)
```

Where:
- `base_confidence`: 0.95 (pdfplumber), 0.75 (OCR), 0.80 (unknown)
- `empty_penalty`: Up to 30% penalty for empty cells

## Error Handling

The validation system gracefully handles:
- Empty tables
- Missing headers
- Inconsistent row lengths
- Missing extraction method metadata

## Testing

Run the example to see validation in action:

```bash
cd backend
python example_validation.py
```

This demonstrates:
1. Basic validation with sample Form 20 data
2. Detection of OCR errors, negative numbers, etc.
3. Integration with conversion flow

## Future Enhancements

Potential improvements:
- Custom validation rules per document type
- Machine learning-based confidence scoring
- Automatic correction suggestions
- Validation rule configuration via API
- Batch validation for multiple tables




