"""
Example usage of the comprehensive data validation system.

This demonstrates how validation works with Form 20 election data.
"""

from app.data_validator import (
    ExtractionValidator,
    StructureValidator,
    DataTypeValidator,
    ConsistencyValidator,
    QualityScorer,
)
from app.models import TableData


def example_validation():
    """Example of validating extracted table data."""
    
    # Create sample TableData (simulating extracted Form 20 data)
    sample_table = TableData(
        headers=[
            "Polling Station No.",
            "Candidate 1 (BJP)",
            "Candidate 2 (INC)",
            "Candidate 3 (DMK)",
            "NOTA",
            "Total Valid Votes",
        ],
        rows=[
            ["1", "150", "200", "180", "10", "540"],
            ["2", "175", "190", "195", "8", "568"],
            ["3", "O", "200", "180", "10", "390"],  # OCR error: O instead of 0
            ["4", "-5", "200", "180", "10", "385"],  # Negative number (error)
            ["5", "150", "200", "180", "10", "540"],
            ["TOTAL", "625", "990", "915", "48", "2578"],
        ],
        extraction_method="ocr",
    )
    
    # Initialize main validator
    validator = ExtractionValidator()
    
    # Validate the table
    result = validator.validate([sample_table], extraction_method="ocr")
    
    print("=" * 60)
    print("VALIDATION RESULTS")
    print("=" * 60)
    print(f"Passed: {result.passed}")
    print(f"Confidence: {result.confidence:.3f}")
    print()
    
    if result.issues:
        print("ISSUES:")
        for issue in result.issues:
            print(f"  ❌ {issue}")
        print()
    
    if result.warnings:
        print("WARNINGS:")
        for warning in result.warnings:
            print(f"  ⚠️  {warning}")
        print()
    
    if result.suggestions:
        print("SUGGESTIONS:")
        for suggestion in result.suggestions:
            print(f"  💡 {suggestion}")
        print()
    
    print("=" * 60)
    
    # Example: Individual validators
    print("\n" + "=" * 60)
    print("INDIVIDUAL VALIDATOR RESULTS")
    print("=" * 60)
    
    structure_validator = StructureValidator()
    structure_result = structure_validator.validate_form20_structure(sample_table)
    print(f"\nStructure Validation:")
    print(f"  Passed: {structure_result.passed}")
    print(f"  Confidence: {structure_result.confidence:.3f}")
    if structure_result.issues:
        print(f"  Issues: {len(structure_result.issues)}")
    
    data_type_validator = DataTypeValidator()
    data_type_result = data_type_validator.validate_numeric_columns(sample_table)
    print(f"\nData Type Validation:")
    print(f"  Passed: {data_type_result.passed}")
    print(f"  Confidence: {data_type_result.confidence:.3f}")
    if data_type_result.issues:
        print(f"  Issues: {len(data_type_result.issues)}")
        for issue in data_type_result.issues[:3]:  # Show first 3
            print(f"    - {issue}")
    
    consistency_validator = ConsistencyValidator()
    consistency_result = consistency_validator.validate_consistency(sample_table)
    print(f"\nConsistency Validation:")
    print(f"  Passed: {consistency_result.passed}")
    print(f"  Confidence: {consistency_result.confidence:.3f}")
    if consistency_result.issues:
        print(f"  Issues: {len(consistency_result.issues)}")
    
    print("=" * 60)


def example_validation_integration():
    """
    Example showing how validation integrates with the conversion flow.
    
    This simulates what happens in process_conversion() in main.py
    """
    
    # Simulate extraction result
    extraction_result_tables = [
        TableData(
            headers=["Polling Station No.", "Candidate 1", "Candidate 2", "NOTA"],
            rows=[
                ["1", "150", "200", "10"],
                ["2", "175", "190", "8"],
            ],
            extraction_method="pdfplumber",
        )
    ]
    
    # Validation phase (as in process_conversion)
    validator = ExtractionValidator()
    extraction_method = extraction_result_tables[0].extraction_method
    validation_result = validator.validate(extraction_result_tables, extraction_method=extraction_method)
    
    # Decision logic (as in process_conversion)
    if validation_result.confidence < 0.7:
        print("⚠️  Low confidence - marking for manual review")
        print(f"   Confidence: {validation_result.confidence:.3f}")
        print(f"   Issues: {len(validation_result.issues)}")
        print(f"   Status: needs_review")
        # Task would be marked as "needs_review" here
    else:
        print("✅ Validation passed - proceeding to Excel creation")
        print(f"   Confidence: {validation_result.confidence:.3f}")
        # Proceed to Excel creation
    

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("EXAMPLE 1: Basic Validation")
    print("=" * 60 + "\n")
    example_validation()
    
    print("\n\n" + "=" * 60)
    print("EXAMPLE 2: Integration with Conversion Flow")
    print("=" * 60 + "\n")
    example_validation_integration()




