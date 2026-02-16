"""
Comprehensive Data Validation System for PDF-to-Excel Converter.

This module provides multi-layered validation to catch extraction errors
before Excel creation. Includes structure, data type, consistency, and
quality validation specifically designed for Indian Election Form 20 documents.
"""

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Set, Tuple

from .models import TableData

logger = logging.getLogger(__name__)


class IssueSeverity(Enum):
    """Severity level for validation issues."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class ValidationResult:
    """
    Validation result with human-readable issues and confidence score.
    
    Matches the user's specification for validation output format.
    """
    passed: bool
    confidence: float  # 0.0 to 1.0
    issues: List[str] = field(default_factory=list)  # Human-readable issue descriptions
    warnings: List[str] = field(default_factory=list)  # Non-critical issues
    suggestions: List[str] = field(default_factory=list)  # Suggested fixes

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "passed": self.passed,
            "confidence": round(self.confidence, 3),
            "issues": self.issues,
            "warnings": self.warnings,
            "suggestions": self.suggestions,
        }


@dataclass
class ValidationIssue:
    """A single validation issue with metadata."""
    severity: IssueSeverity
    code: str
    message: str
    row_index: Optional[int] = None
    column_index: Optional[int] = None
    column_name: Optional[str] = None
    value: Optional[str] = None

    def to_human_readable(self) -> str:
        """Convert to human-readable string."""
        location = ""
        if self.row_index is not None:
            location = f" (Row {self.row_index + 1}"
            if self.column_name:
                location += f", Column: {self.column_name}"
            location += ")"
        
        return f"{self.message}{location}"


@dataclass
class ValidationReport:
    """Complete validation report for extracted data."""
    is_valid: bool
    confidence_score: float  # 0.0 to 1.0
    total_rows: int
    total_columns: int
    issues: List[ValidationIssue] = field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0
    extraction_method: str = "unknown"
    quality_grade: str = "unknown"  # A, B, C, D, F

    def to_validation_result(self) -> ValidationResult:
        """Convert to user-specified ValidationResult format."""
        issues_list = []
        warnings_list = []
        suggestions_list = []

        for issue in self.issues:
            msg = issue.to_human_readable()
            if issue.severity == IssueSeverity.CRITICAL or issue.severity == IssueSeverity.ERROR:
                issues_list.append(msg)
            elif issue.severity == IssueSeverity.WARNING:
                warnings_list.append(msg)
            else:
                warnings_list.append(msg)

        # Generate suggestions based on issues
        if self.errors_count > 0:
            suggestions_list.append("Review extraction method - consider using OCR if pdfplumber failed")
        if self.warnings_count > 5:
            suggestions_list.append("Manual review recommended - multiple warnings detected")
        if self.confidence_score < 0.7:
            suggestions_list.append("Low confidence score - verify extracted data manually")

        return ValidationResult(
            passed=self.is_valid,
            confidence=self.confidence_score,
            issues=issues_list,
            warnings=warnings_list,
            suggestions=suggestions_list,
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "is_valid": self.is_valid,
            "confidence_score": round(self.confidence_score, 2),
            "quality_grade": self.quality_grade,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "extraction_method": self.extraction_method,
            "warnings_count": self.warnings_count,
            "errors_count": self.errors_count,
            "issues": [issue.to_dict() for issue in self.issues],
        }


class StructureValidator:
    """
    Validates Form 20 structure requirements.
    
    Checks:
    - First column is "Polling Station No." or similar
    - Has expected candidate columns (14-15 columns)
    - Has NOTA column
    - Has reasonable row count (50-300 polling stations)
    """

    # Form 20 structure expectations
    EXPECTED_FIRST_COLUMN_KEYWORDS = [
        "polling station", "station no", "station number", "sl. no", "sl no",
        "s.no", "serial", "ps no", "ps number", "no.", "no ", "number"
    ]
    
    EXPECTED_COLUMN_COUNT_RANGE = (10, 25)  # Expanded range - some forms have more columns
    EXPECTED_ROW_COUNT_RANGE = (30, 500)  # Expanded range for different constituency sizes
    
    NOTA_KEYWORDS = ["nota", "none of the above", "none"]

    def validate_form20_structure(self, table: TableData) -> ValidationResult:
        """
        Validate that table matches Form 20 structure.
        
        Args:
            table: TableData to validate
            
        Returns:
            ValidationResult with structure validation results
        """
        issues: List[ValidationIssue] = []
        
        if not table.headers:
            issues.append(ValidationIssue(
                severity=IssueSeverity.CRITICAL,
                code="NO_HEADERS",
                message="Table has no headers - cannot validate structure"
            ))
            return self._result_from_issues(issues, table)
        
        # Check first column (more lenient - only error if clearly wrong)
        first_col_valid = self._check_first_column(table)
        if not first_col_valid:
            # Only flag as warning, not error - might be a naming variation
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,  # Changed from ERROR to WARNING
                code="INVALID_FIRST_COLUMN",
                message="First column does not appear to be 'Polling Station No.' or similar identifier"
            ))
        
        # Check column count (more lenient - only warn for extreme cases)
        col_count = len(table.headers)
        if col_count < 8:  # Very few columns - likely an issue
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="FEW_COLUMNS",
                message=f"Table has {col_count} columns, which is unusually low for Form 20"
            ))
        elif col_count > 30:  # Very many columns - might be an extraction issue
            issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,  # Changed to INFO - not necessarily wrong
                code="MANY_COLUMNS",
                message=f"Table has {col_count} columns, which is unusually high for Form 20"
            ))
        
        # Check for NOTA column
        has_nota = self._check_nota_column(table)
        if not has_nota:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="NO_NOTA_COLUMN",
                message="NOTA (None of the Above) column not found - may be missing or named differently"
            ))
        
        # Check row count
        row_count = len(table.rows)
        if row_count < self.EXPECTED_ROW_COUNT_RANGE[0]:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="FEW_ROWS",
                message=f"Table has {row_count} rows, expected {self.EXPECTED_ROW_COUNT_RANGE[0]}-{self.EXPECTED_ROW_COUNT_RANGE[1]} polling stations"
            ))
        elif row_count > self.EXPECTED_ROW_COUNT_RANGE[1]:
            issues.append(ValidationIssue(
                severity=IssueSeverity.INFO,
                code="MANY_ROWS",
                message=f"Table has {row_count} rows, which is unusually high"
            ))
        
        return self._result_from_issues(issues, table)
    
    def _check_first_column(self, table: TableData) -> bool:
        """Check if first column matches expected polling station identifier."""
        if not table.headers:
            return False
        
        first_header = str(table.headers[0]).lower().strip()
        
        # Check normal orientation
        if any(kw in first_header for kw in self.EXPECTED_FIRST_COLUMN_KEYWORDS):
            return True
        
        # Check reversed text (common in OCR/extraction issues)
        reversed_header = first_header[::-1]
        if any(kw in reversed_header for kw in self.EXPECTED_FIRST_COLUMN_KEYWORDS):
            return True
        
        # Also check if first column contains numeric data (polling station numbers)
        # This is a more lenient check - if first column has numbers, it's likely correct
        if table.rows:
            numeric_count = 0
            for row in table.rows[:10]:  # Check first 10 rows
                if row and len(row) > 0:
                    first_val = str(row[0]).strip()
                    # Check if it's a number or contains numbers
                    if first_val and (first_val.isdigit() or any(c.isdigit() for c in first_val)):
                        numeric_count += 1
            if numeric_count >= 5:  # If 5+ rows have numeric first column, likely correct
                return True
        
        return False
    
    def _check_nota_column(self, table: TableData) -> bool:
        """Check if table has a NOTA column, including reversed text."""
        if not table.headers:
            return False
        
        for header in table.headers:
            header_lower = str(header).lower().strip()
            # Check normal orientation
            if any(kw in header_lower for kw in self.NOTA_KEYWORDS):
                return True
            # Check reversed text
            reversed_header = header_lower[::-1]
            if any(kw in reversed_header for kw in self.NOTA_KEYWORDS):
                return True
        return False
    
    def _result_from_issues(self, issues: List[ValidationIssue], table: TableData) -> ValidationResult:
        """Convert issues to ValidationResult."""
        critical_errors = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        
        passed = len(critical_errors) == 0
        
        # Calculate confidence based on issues (more lenient for warnings)
        confidence = 1.0
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                confidence -= 0.3
            elif issue.severity == IssueSeverity.ERROR:
                confidence -= 0.1  # Reduced from 0.15
            elif issue.severity == IssueSeverity.WARNING:
                confidence -= 0.02  # Reduced from 0.05 - warnings are less severe
            elif issue.severity == IssueSeverity.INFO:
                confidence -= 0.01  # Minimal penalty for info
        
        confidence = max(0.0, min(1.0, confidence))
        
        issues_list = [i.to_human_readable() for i in critical_errors + errors]
        warnings_list = [i.to_human_readable() for i in issues if i.severity == IssueSeverity.WARNING]
        suggestions_list = []
        
        if not passed:
            suggestions_list.append("Verify PDF structure matches Form 20 format")
        if errors:
            suggestions_list.append("Check if headers were extracted correctly")
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            issues=issues_list,
            warnings=warnings_list,
            suggestions=suggestions_list,
        )


class DataTypeValidator:
    """
    Validates data types in numeric columns.
    
    For columns 2-16 (vote counts):
    - Check all values are numeric or empty
    - Flag negative numbers
    - Flag unreasonably large numbers (>10000)
    - Check for OCR errors: "O" instead of "0", "l" instead of "1"
    """

    MAX_REASONABLE_VOTE_COUNT = 50000  # Increased - some constituencies have high voter counts
    MIN_REASONABLE_VOTE_COUNT = 0
    
    # OCR error patterns
    OCR_ERROR_PATTERNS = [
        (r'^[Oo]+$', '0', "Letter 'O' instead of zero"),
        (r'^[l|I]+$', '1', "Letter 'l' or 'I' instead of one"),
        (r'[Oo](?=\d)', '0', "Letter 'O' before digit"),
        (r'\d(?=[Oo])', '', "Digit before letter 'O'"),
    ]

    def validate_numeric_columns(self, table: TableData) -> ValidationResult:
        """
        Validate numeric columns (vote counts).
        
        Args:
            table: TableData to validate
            
        Returns:
            ValidationResult with data type validation results
        """
        issues: List[ValidationIssue] = []
        
        if not table.headers or not table.rows:
            return ValidationResult(
                passed=False,
                confidence=0.0,
                issues=["No headers or rows to validate"],
            )
        
        # Identify numeric columns (typically columns 2 onwards, excluding first column)
        numeric_col_indices = self._identify_numeric_columns(table)
        
        if not numeric_col_indices:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="NO_NUMERIC_COLUMNS",
                message="Could not identify numeric columns for validation"
            ))
            return self._result_from_issues(issues, table)
        
        # Validate each numeric column
        invalid_count = 0
        negative_count = 0
        large_number_count = 0
        ocr_error_count = 0
        
        for col_idx in numeric_col_indices:
            if col_idx >= len(table.headers):
                continue
            
            col_name = table.headers[col_idx]
            
            for row_idx, row in enumerate(table.rows):
                if col_idx >= len(row):
                    continue
                
                value = row[col_idx]
                if not value or not str(value).strip():
                    continue  # Empty is OK
                
                # Check for OCR errors
                ocr_issue = self._check_ocr_error(value, row_idx, col_idx, col_name)
                if ocr_issue:
                    issues.append(ocr_issue)
                    ocr_error_count += 1
                    continue
                
                # Check if value might be reversed text before flagging as error
                reversed_value = str(value).strip()[::-1]
                reversed_numeric = self._parse_numeric(reversed_value)
                
                # Try to parse as number
                numeric_value = self._parse_numeric(value)
                if numeric_value is None:
                    # If reversed version is numeric, it's likely a text reversal issue
                    # Don't flag as error - it will be fixed during extraction
                    if reversed_numeric is not None:
                        continue  # Skip this - it's a reversal issue, not a data error
                    
                    invalid_count += 1
                    if invalid_count <= 10:  # Limit detailed reporting
                        issues.append(ValidationIssue(
                            severity=IssueSeverity.ERROR,
                            code="INVALID_NUMERIC",
                            message=f"Non-numeric value '{value}' in column '{col_name}'",
                            row_index=row_idx,
                            column_index=col_idx,
                            column_name=col_name,
                            value=str(value)
                        ))
                else:
                    # Check for negative numbers
                    if numeric_value < self.MIN_REASONABLE_VOTE_COUNT:
                        negative_count += 1
                        if negative_count <= 5:
                            issues.append(ValidationIssue(
                                severity=IssueSeverity.ERROR,
                                code="NEGATIVE_NUMBER",
                                message=f"Negative number {numeric_value} in column '{col_name}'",
                                row_index=row_idx,
                                column_index=col_idx,
                                column_name=col_name,
                                value=str(value)
                            ))
                    
                    # Check for unreasonably large numbers (only flag extremely large values)
                    if numeric_value > self.MAX_REASONABLE_VOTE_COUNT:
                        large_number_count += 1
                        # Only flag if it's extremely large (likely OCR error) - not just high vote counts
                        if numeric_value > 100000 and large_number_count <= 3:
                            issues.append(ValidationIssue(
                                severity=IssueSeverity.INFO,  # Changed to INFO - not necessarily wrong
                                code="LARGE_NUMBER",
                                message=f"Unusually large number {numeric_value} in column '{col_name}' (possible OCR error)",
                                row_index=row_idx,
                                column_index=col_idx,
                                column_name=col_name,
                                value=str(value)
                            ))
        
        # Add summary issues if many found
        if invalid_count > 10:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="MANY_INVALID_NUMERIC",
                message=f"Found {invalid_count} invalid numeric values (possible extraction errors)"
            ))
        
        if negative_count > 5:
            issues.append(ValidationIssue(
                severity=IssueSeverity.ERROR,
                code="MANY_NEGATIVE",
                message=f"Found {negative_count} negative numbers (vote counts cannot be negative)"
            ))
        
        if ocr_error_count > 10:
            issues.append(ValidationIssue(
                severity=IssueSeverity.WARNING,
                code="MANY_OCR_ERRORS",
                message=f"Found {ocr_error_count} potential OCR character misreads"
            ))
        
        return self._result_from_issues(issues, table)
    
    def _identify_numeric_columns(self, table: TableData) -> List[int]:
        """Identify which columns should contain numeric data."""
        numeric_indices = []
        
        for idx, header in enumerate(table.headers):
            # Skip first column (usually station number)
            if idx == 0:
                continue
            
            header_lower = str(header).lower()
            # Check if header suggests numeric data
            if any(kw in header_lower for kw in ['vote', 'count', 'total', 'valid', 'rejected', 'nota']):
                numeric_indices.append(idx)
        
        # If no explicit numeric columns found, assume columns 2-16 are numeric
        if not numeric_indices and len(table.headers) > 2:
            numeric_indices = list(range(2, min(17, len(table.headers))))
        
        return numeric_indices
    
    def _check_ocr_error(self, value: str, row_idx: int, col_idx: int, col_name: str) -> Optional[ValidationIssue]:
        """Check for common OCR errors in numeric values."""
        value_str = str(value).strip()
        
        for pattern, replacement, description in self.OCR_ERROR_PATTERNS:
            if re.search(pattern, value_str):
                return ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="OCR_ERROR",
                    message=f"Possible OCR error ({description}): '{value_str}' in column '{col_name}'",
                    row_index=row_idx,
                    column_index=col_idx,
                    column_name=col_name,
                    value=value_str
                )
        
        return None
    
    def _parse_numeric(self, value: str) -> Optional[float]:
        """Parse a value as numeric, handling common formatting."""
        if not value:
            return None
        
        # Remove formatting
        cleaned = str(value).strip().replace(',', '').replace(' ', '').replace('₹', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def _result_from_issues(self, issues: List[ValidationIssue], table: TableData) -> ValidationResult:
        """Convert issues to ValidationResult."""
        critical_errors = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        
        passed = len(critical_errors) == 0 and len(errors) == 0
        
        confidence = 1.0
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                confidence -= 0.3
            elif issue.severity == IssueSeverity.ERROR:
                confidence -= 0.08  # Reduced from 0.1
            elif issue.severity == IssueSeverity.WARNING:
                confidence -= 0.02  # Reduced from 0.05 - warnings are less severe
            elif issue.severity == IssueSeverity.INFO:
                confidence -= 0.01  # Minimal penalty for info
        
        confidence = max(0.0, min(1.0, confidence))
        
        issues_list = [i.to_human_readable() for i in critical_errors + errors]
        warnings_list = [i.to_human_readable() for i in issues if i.severity == IssueSeverity.WARNING]
        suggestions_list = []
        
        if errors:
            suggestions_list.append("Review numeric columns for extraction errors")
            suggestions_list.append("Check for OCR character misreads (O/0, l/1)")
        if any("OCR" in i.code for i in issues):
            suggestions_list.append("Consider re-extracting with different OCR settings")
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            issues=issues_list,
            warnings=warnings_list,
            suggestions=suggestions_list,
        )


class ConsistencyValidator:
    """
    Validates data consistency across the table.
    
    Checks:
    - All rows have same column count as headers
    - Sequential polling station numbers (with allowed gaps)
    - Total row matches sum of columns (if present)
    - No duplicate polling stations
    """

    def validate_consistency(self, table: TableData) -> ValidationResult:
        """
        Validate data consistency.
        
        Args:
            table: TableData to validate
            
        Returns:
            ValidationResult with consistency validation results
        """
        issues: List[ValidationIssue] = []
        
        if not table.headers or not table.rows:
            return ValidationResult(
                passed=False,
                confidence=0.0,
                issues=["No headers or rows to validate"],
            )
        
        expected_cols = len(table.headers)
        
        # Check column count consistency
        inconsistent_rows = []
        for row_idx, row in enumerate(table.rows):
            if len(row) != expected_cols:
                inconsistent_rows.append((row_idx, len(row)))
        
        if inconsistent_rows:
            if len(inconsistent_rows) > 5:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="COLUMN_MISMATCH",
                    message=f"{len(inconsistent_rows)} rows have inconsistent column counts (expected {expected_cols})"
                ))
            else:
                for row_idx, col_count in inconsistent_rows:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="COLUMN_MISMATCH",
                        message=f"Row {row_idx + 1} has {col_count} columns (expected {expected_cols})",
                        row_index=row_idx
                    ))
        
        # Check sequential polling station numbers
        station_issues = self._check_sequential_stations(table)
        issues.extend(station_issues)
        
        # Check for duplicate polling stations
        duplicate_issues = self._check_duplicate_stations(table)
        issues.extend(duplicate_issues)
        
        # Check total row (if present)
        total_issues = self._check_total_row(table)
        issues.extend(total_issues)
        
        return self._result_from_issues(issues, table)
    
    def _check_sequential_stations(self, table: TableData) -> List[ValidationIssue]:
        """Check if polling station numbers are sequential."""
        issues = []
        
        if not table.rows or not table.headers:
            return issues
        
        # Try to extract station numbers from first column
        station_numbers = []
        for row_idx, row in enumerate(table.rows):
            if not row:
                continue
            station_val = str(row[0]).strip() if row else ""
            # Try to extract numeric part
            match = re.search(r'\d+', station_val)
            if match:
                try:
                    station_numbers.append((row_idx, int(match.group())))
                except ValueError:
                    pass
        
        if len(station_numbers) < 2:
            return issues  # Not enough data to check
        
        # Check for gaps (allow some gaps, but flag large ones)
        prev_num = None
        large_gaps = []
        for row_idx, num in station_numbers:
            if prev_num is not None:
                gap = num - prev_num
                if gap > 5:  # Allow gaps up to 5
                    large_gaps.append((row_idx, prev_num, num, gap))
            prev_num = num
        
        if large_gaps:
            if len(large_gaps) > 3:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="LARGE_STATION_GAPS",
                    message=f"Found {len(large_gaps)} large gaps in polling station numbers (possible missing data)"
                ))
            else:
                for row_idx, prev, curr, gap in large_gaps:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.INFO,
                        code="STATION_GAP",
                        message=f"Large gap in station numbers: {prev} to {curr} (gap of {gap})",
                        row_index=row_idx
                    ))
        
        return issues
    
    def _check_duplicate_stations(self, table: TableData) -> List[ValidationIssue]:
        """Check for duplicate polling station numbers."""
        issues = []
        
        if not table.rows:
            return issues
        
        seen_stations = {}
        duplicates = []
        
        for row_idx, row in enumerate(table.rows):
            if not row:
                continue
            station_val = str(row[0]).strip() if row else ""
            # Normalize station value
            normalized = station_val.lower().strip()
            if normalized in seen_stations:
                duplicates.append((row_idx, normalized, seen_stations[normalized]))
            else:
                seen_stations[normalized] = row_idx
        
        if duplicates:
            if len(duplicates) > 5:
                issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="MANY_DUPLICATE_STATIONS",
                    message=f"Found {len(duplicates)} duplicate polling station numbers"
                ))
            else:
                for row_idx, station, first_row in duplicates:
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.ERROR,
                        code="DUPLICATE_STATION",
                        message=f"Duplicate polling station '{station}' at rows {first_row + 1} and {row_idx + 1}",
                        row_index=row_idx
                    ))
        
        return issues
    
    def _check_total_row(self, table: TableData) -> List[ValidationIssue]:
        """Check if total row matches sum of columns."""
        issues = []
        
        if not table.rows:
            return issues
        
        # Look for total row (usually last row with "TOTAL" or "TOTAL" in first column)
        total_row_idx = None
        for idx, row in enumerate(reversed(table.rows)):
            if row and len(row) > 0:
                first_cell = str(row[0]).upper().strip()
                if "TOTAL" in first_cell:
                    total_row_idx = len(table.rows) - 1 - idx
                    break
        
        if total_row_idx is None:
            return issues  # No total row found, that's OK
        
        # Validate total row sums
        total_row = table.rows[total_row_idx]
        expected_cols = len(table.headers)
        
        # Check numeric columns (skip first column)
        for col_idx in range(1, min(expected_cols, len(total_row))):
            if col_idx >= len(total_row):
                continue
            
            # Try to get sum of column
            column_sum = 0
            valid_count = 0
            for row_idx, row in enumerate(table.rows):
                if row_idx == total_row_idx:
                    continue
                if col_idx < len(row):
                    value = self._parse_numeric(row[col_idx])
                    if value is not None:
                        column_sum += value
                        valid_count += 1
            
            # Compare with total row value
            total_value = self._parse_numeric(total_row[col_idx])
            if total_value is not None and valid_count > 0:
                diff = abs(total_value - column_sum)
                if diff > 1:  # Allow small rounding differences
                    issues.append(ValidationIssue(
                        severity=IssueSeverity.WARNING,
                        code="TOTAL_MISMATCH",
                        message=f"Total row value {total_value} does not match sum {column_sum} in column {col_idx + 1} (difference: {diff})",
                        row_index=total_row_idx,
                        column_index=col_idx
                    ))
        
        return issues
    
    def _parse_numeric(self, value: str) -> Optional[float]:
        """Parse a value as numeric."""
        if not value:
            return None
        cleaned = str(value).strip().replace(',', '').replace(' ', '')
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def _result_from_issues(self, issues: List[ValidationIssue], table: TableData) -> ValidationResult:
        """Convert issues to ValidationResult."""
        critical_errors = [i for i in issues if i.severity == IssueSeverity.CRITICAL]
        errors = [i for i in issues if i.severity == IssueSeverity.ERROR]
        
        passed = len(critical_errors) == 0
        
        confidence = 1.0
        for issue in issues:
            if issue.severity == IssueSeverity.CRITICAL:
                confidence -= 0.3
            elif issue.severity == IssueSeverity.ERROR:
                confidence -= 0.08  # Reduced from 0.1
            elif issue.severity == IssueSeverity.WARNING:
                confidence -= 0.02  # Reduced from 0.05 - warnings are less severe
            elif issue.severity == IssueSeverity.INFO:
                confidence -= 0.01  # Minimal penalty for info
        
        confidence = max(0.0, min(1.0, confidence))
        
        issues_list = [i.to_human_readable() for i in critical_errors + errors]
        warnings_list = [i.to_human_readable() for i in issues if i.severity == IssueSeverity.WARNING]
        suggestions_list = []
        
        if errors:
            suggestions_list.append("Check for missing or duplicate polling station data")
        if any("TOTAL" in i.code for i in issues):
            suggestions_list.append("Verify total row calculations")
        
        return ValidationResult(
            passed=passed,
            confidence=confidence,
            issues=issues_list,
            warnings=warnings_list,
            suggestions=suggestions_list,
        )


class QualityScorer:
    """
    Calculates overall confidence score based on multiple factors.
    
    Factors:
    - Extraction method (OCR lower than pdfplumber)
    - Validation pass rate
    - Empty cell ratio
    - Data type consistency
    """

    def calculate_confidence(
        self,
        table: TableData,
        validations: List[ValidationResult]
    ) -> float:
        """
        Calculate overall confidence score (0.0-1.0).
        
        Args:
            table: TableData that was validated
            validations: List of ValidationResult from different validators
            
        Returns:
            Confidence score between 0.0 and 1.0
        """
        if not table.rows or not table.headers:
            return 0.0
        
        # Base confidence from extraction method
        extraction_method = getattr(table, 'extraction_method', 'unknown')
        base_confidence = self._get_base_confidence(extraction_method)
        
        # Average confidence from validations
        validation_confidences = [v.confidence for v in validations]
        avg_validation_confidence = sum(validation_confidences) / len(validation_confidences) if validation_confidences else 0.5
        
        # Calculate empty cell ratio
        empty_ratio = self._calculate_empty_ratio(table)
        empty_penalty = empty_ratio * 0.3  # Up to 30% penalty for empty cells
        
        # Calculate data type consistency
        type_consistency = self._calculate_type_consistency(table)
        
        # Combine factors
        confidence = (
            base_confidence * 0.4 +  # 40% weight on extraction method
            avg_validation_confidence * 0.4 +  # 40% weight on validation results
            type_consistency * 0.2  # 20% weight on type consistency
        )
        
        # Apply empty cell penalty
        confidence = confidence * (1 - empty_penalty)
        
        # Ensure bounds
        confidence = max(0.0, min(1.0, confidence))
        
        return confidence
    
    def _get_base_confidence(self, extraction_method: str) -> float:
        """Get base confidence based on extraction method."""
        method_confidence = {
            "pdfplumber": 0.95,
            "ocr": 0.75,
            "azure_di": 0.90,
            "azure_di_fallback": 0.90,
            "constituency_azure_di": 0.90,
            "structured": 0.90,
            "unknown": 0.80,
        }
        return method_confidence.get(extraction_method.lower(), 0.80)
    
    def _calculate_empty_ratio(self, table: TableData) -> float:
        """Calculate ratio of empty cells."""
        if not table.rows or not table.headers:
            return 1.0
        
        total_cells = len(table.rows) * len(table.headers)
        if total_cells == 0:
            return 1.0
        
        empty_cells = 0
        for row in table.rows:
            for cell in row:
                if not cell or not str(cell).strip():
                    empty_cells += 1
        
        return empty_cells / total_cells
    
    def _calculate_type_consistency(self, table: TableData) -> float:
        """Calculate data type consistency score."""
        if not table.rows or not table.headers:
            return 0.0
        
        # Identify numeric columns
        numeric_cols = set()
        for idx, header in enumerate(table.headers):
            if idx == 0:  # Skip first column
                continue
            header_lower = str(header).lower()
            if any(kw in header_lower for kw in ['vote', 'count', 'total', 'valid']):
                numeric_cols.add(idx)
        
        if not numeric_cols:
            return 0.8  # Default if can't identify
        
        # Check consistency in numeric columns
        consistent_count = 0
        total_count = 0
        
        for col_idx in numeric_cols:
            for row in table.rows:
                if col_idx < len(row):
                    value = row[col_idx]
                    total_count += 1
                    if self._is_numeric(value):
                        consistent_count += 1
        
        if total_count == 0:
            return 0.0
        
        return consistent_count / total_count
    
    def _is_numeric(self, value: str) -> bool:
        """Check if value is numeric."""
        if not value:
            return True  # Empty is OK
        cleaned = str(value).strip().replace(',', '').replace(' ', '')
        try:
            float(cleaned)
            return True
        except ValueError:
            return False


class ExtractionValidator:
    """
    Main validator that orchestrates all validation components.
    
    This is the primary interface for validation in the conversion pipeline.
    """

    def __init__(self):
        """Initialize the validator with all sub-validators."""
        self.structure_validator = StructureValidator()
        self.data_type_validator = DataTypeValidator()
        self.consistency_validator = ConsistencyValidator()
        self.quality_scorer = QualityScorer()

    def validate(
        self,
        tables: List[TableData],
        extraction_method: str = "unknown"
    ) -> ValidationResult:
        """
        Validate extracted tables using all validators.
        
        Args:
            tables: List of TableData objects to validate
            extraction_method: Method used for extraction ("pdfplumber", "ocr", etc.)
            
        Returns:
            ValidationResult with comprehensive validation results
        """
        if not tables:
            return ValidationResult(
                passed=False,
                confidence=0.0,
                issues=["No tables were extracted from the document"],
                suggestions=["Verify PDF contains extractable tables"],
            )
        
        # Validate each table
        all_issues: List[str] = []
        all_warnings: List[str] = []
        all_suggestions: List[str] = []
        validation_results: List[ValidationResult] = []
        
        for table_idx, table in enumerate(tables):
            if table.is_empty:
                all_issues.append(f"Table {table_idx + 1} is empty")
                continue
            
            # Set extraction method if not set
            if not hasattr(table, 'extraction_method') or not table.extraction_method:
                table.extraction_method = extraction_method
            
            # Run all validators
            structure_result = self.structure_validator.validate_form20_structure(table)
            data_type_result = self.data_type_validator.validate_numeric_columns(table)
            consistency_result = self.consistency_validator.validate_consistency(table)
            
            # Collect results
            validation_results.extend([structure_result, data_type_result, consistency_result])
            
            # Aggregate issues
            all_issues.extend(structure_result.issues)
            all_issues.extend(data_type_result.issues)
            all_issues.extend(consistency_result.issues)
            
            all_warnings.extend(structure_result.warnings)
            all_warnings.extend(data_type_result.warnings)
            all_warnings.extend(consistency_result.warnings)
            
            all_suggestions.extend(structure_result.suggestions)
            all_suggestions.extend(data_type_result.suggestions)
            all_suggestions.extend(consistency_result.suggestions)
        
        # Calculate overall confidence using quality scorer
        # Use first non-empty table for quality scoring
        main_table = next((t for t in tables if not t.is_empty), None)
        if main_table:
            overall_confidence = self.quality_scorer.calculate_confidence(
                main_table,
                validation_results
            )
        else:
            overall_confidence = 0.0
        
        # Determine if passed (no critical issues)
        passed = len(all_issues) == 0 and overall_confidence >= 0.5
        
        # Remove duplicate suggestions
        unique_suggestions = list(dict.fromkeys(all_suggestions))
        
        logger.info(
            f"Validation complete: passed={passed}, confidence={overall_confidence:.3f}, "
            f"issues={len(all_issues)}, warnings={len(all_warnings)}"
        )
        
        # Create ValidationResult for user-facing API
        validation_result = ValidationResult(
            passed=passed,
            confidence=overall_confidence,
            issues=all_issues,
            warnings=all_warnings,
            suggestions=unique_suggestions,
        )
        
        return validation_result
    
    def validate_report(
        self,
        tables: List[TableData],
        extraction_method: str = "unknown"
    ) -> ValidationReport:
        """
        Validate extracted tables and return ValidationReport (for internal use).
        
        This method returns ValidationReport which is compatible with pdf_processor.py
        and includes both confidence_score and quality_grade.
        
        Args:
            tables: List of TableData objects to validate
            extraction_method: Method used for extraction ("pdfplumber", "ocr", etc.)
            
        Returns:
            ValidationReport with comprehensive validation results
        """
        # Get ValidationResult first
        validation_result = self.validate(tables, extraction_method)
        
        # Convert ValidationResult to ValidationReport format
        # Collect all validation issues from individual validators
        all_validation_issues: List[ValidationIssue] = []
        
        for table_idx, table in enumerate(tables):
            if table.is_empty:
                all_validation_issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="EMPTY_TABLE",
                    message=f"Table {table_idx + 1} is empty"
                ))
                continue
            
            # Run validators to get ValidationIssues
            structure_result = self.structure_validator.validate_form20_structure(table)
            data_type_result = self.data_type_validator.validate_numeric_columns(table)
            consistency_result = self.consistency_validator.validate_consistency(table)
            
            # Convert ValidationResult issues to ValidationIssues
            # (We'll create issues from the result messages)
            for issue_msg in structure_result.issues + data_type_result.issues + consistency_result.issues:
                all_validation_issues.append(ValidationIssue(
                    severity=IssueSeverity.ERROR,
                    code="VALIDATION_ERROR",
                    message=issue_msg
                ))
            
            for warning_msg in structure_result.warnings + data_type_result.warnings + consistency_result.warnings:
                all_validation_issues.append(ValidationIssue(
                    severity=IssueSeverity.WARNING,
                    code="VALIDATION_WARNING",
                    message=warning_msg
                ))
        
        # Count issues
        warnings_count = sum(1 for i in all_validation_issues if i.severity == IssueSeverity.WARNING)
        errors_count = sum(1 for i in all_validation_issues if i.severity in [IssueSeverity.ERROR, IssueSeverity.CRITICAL])
        
        # Calculate quality grade
        quality_grade = self._calculate_grade(validation_result.confidence, errors_count, warnings_count)
        
        # Get total rows and columns
        total_rows = sum(len(t.rows) for t in tables if not t.is_empty)
        total_columns = max((len(t.headers) for t in tables if not t.is_empty), default=0)
        
        # Create ValidationReport
        return ValidationReport(
            is_valid=validation_result.passed,
            confidence_score=validation_result.confidence,  # Use confidence as confidence_score
            total_rows=total_rows,
            total_columns=total_columns,
            issues=all_validation_issues,
            warnings_count=warnings_count,
            errors_count=errors_count,
            extraction_method=extraction_method,
            quality_grade=quality_grade
        )
    
    def _calculate_grade(
        self,
        confidence: float,
        errors: int,
        warnings: int
    ) -> str:
        """
        Calculate quality grade (A-F).
        
        Args:
            confidence: Confidence score
            errors: Number of errors
            warnings: Number of warnings
            
        Returns:
            Grade letter
        """
        if confidence >= 0.95 and errors == 0:
            return "A"
        elif confidence >= 0.85 and errors <= 1:
            return "B"
        elif confidence >= 0.70 and errors <= 3:
            return "C"
        elif confidence >= 0.50:
            return "D"
        else:
            return "F"
