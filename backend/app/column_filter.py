"""Service for filtering Excel columns based on user selection."""

import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

logger = logging.getLogger(__name__)


class ColumnFilterService:
    """Service to filter Excel files by selected columns."""

    def __init__(self):
        """Initialize the column filter service."""
        pass

    def filter_columns(
        self,
        input_file: str,
        requested_columns: List[str],
        output_dir: str,
        include_others: bool = False,
        header_overrides: Optional[Dict[str, str]] = None,
    ) -> tuple[str, dict]:
        """
        Filter Excel file to include only requested columns.

        Args:
            input_file: Path to the source Excel file
            requested_columns: List of column names to include (in desired order)
            output_dir: Directory to save the filtered Excel file
            include_others: If True, add an "OTHER Votes" column with sum of unselected party columns

        Returns:
            Tuple of (output_file_path, metadata_dict)

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If requested columns don't exist in the Excel file
        """
        input_path = Path(input_file)
        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_file}")

        logger.info(f"Loading Excel file: {input_file}")

        # First, use openpyxl to find the correct header row and extract column names
        # (same logic as preview endpoint)
        import openpyxl
        wb = openpyxl.load_workbook(input_file, data_only=True)
        ws = wb.active
        
        # Find actual data range
        actual_max_row = ws.max_row if ws.max_row else 0
        actual_max_col = ws.max_column if ws.max_column else 0
        
        # Find data start row (skip title rows)
        data_start_row = 1
        for row in range(1, min(20, actual_max_row + 1)):
            cell_value = ws.cell(row, 1).value
            if cell_value and str(cell_value).strip():
                # Check if this row looks like headers (has multiple non-empty cells)
                non_empty_count = sum(
                    1 for col in range(1, min(actual_max_col + 1, 20))
                    if ws.cell(row, col).value and str(ws.cell(row, col).value).strip()
                )
                if non_empty_count >= 2:  # At least 2 columns with data
                    data_start_row = row
                    break
        
        # Extract headers by merging multi-row headers
        # Many election PDFs have 2-3 header rows (main header + candidate name + party)
        # This ensures column names match between preview and filter operations
        headers = []
        for col in range(1, actual_max_col + 1):
            # Get values from up to 3 header rows
            header_parts = []
            
            # Check up to 3 rows for header information
            for header_row in range(data_start_row, min(data_start_row + 3, actual_max_row + 1)):
                value = ws.cell(header_row, col).value
                if value is not None and str(value).strip():
                    clean_value = str(value).strip()
                    # Skip generic phrases and party abbreviation labels
                    if clean_value.upper() not in ['PARTY ABBREVIATION', 'NO. OF VALID VOTES CAST IN FAVOUR OF']:
                        header_parts.append(clean_value)
            
            # Combine header parts into a single name
            if header_parts:
                # Use the last non-empty part (usually the party name or most specific info)
                # Or combine if there are multiple meaningful parts
                if len(header_parts) == 1:
                    headers.append(header_parts[0])
                else:
                    # For multi-part headers, prioritize party names (usually in last row)
                    # and candidate names
                    combined = " - ".join(header_parts[-2:]) if len(header_parts) >= 2 else header_parts[-1]
                    headers.append(combined)
            else:
                # Fallback for empty columns
                headers.append(f"Column {col}")
        
        # Find where actual data starts (first row with numeric data in first column)
        first_data_row = data_start_row + 1
        for row in range(data_start_row + 1, min(data_start_row + 10, actual_max_row + 1)):
            cell_val = ws.cell(row, 1).value
            # Check if this looks like data (numeric or starts with a number)
            if cell_val is not None:
                if isinstance(cell_val, (int, float)) or (isinstance(cell_val, str) and str(cell_val).strip().isdigit()):
                    first_data_row = row
                    break
        
        wb.close()
        
        # Now load with pandas, skipping all header rows
        # Skip rows before data, then set our custom column names
        skip_rows = list(range(0, first_data_row - 1))  # 0-indexed, skip everything before data
        df = pd.read_excel(input_file, engine='openpyxl', skiprows=skip_rows, names=headers)

        # Get actual columns from Excel (now using our custom headers)
        available_columns = df.columns.tolist()
        logger.info(f"Available columns: {available_columns}")
        logger.info(f"Requested columns: {requested_columns}")

        # Validate that all requested columns exist
        missing_columns = [col for col in requested_columns if col not in available_columns]
        if missing_columns:
            raise ValueError(
                f"Requested columns not found in Excel file: {missing_columns}. "
                f"Available columns: {available_columns}"
            )

        # Filter dataframe to requested columns (preserving order)
        filtered_df = df[requested_columns].copy()

        # Add OTHERS column if requested
        others_columns = []
        if include_others:
            # Get all unselected numeric columns
            unselected_columns = [col for col in available_columns if col not in requested_columns]
            
            # Filter to only numeric columns
            numeric_unselected = []
            for col in unselected_columns:
                # Check if column is numeric by sampling data
                sample_values = df[col].dropna().head(10)
                if len(sample_values) > 0:
                    numeric_count = pd.to_numeric(sample_values, errors='coerce').notna().sum()
                    if numeric_count / len(sample_values) >= 0.5:  # At least 50% numeric
                        numeric_unselected.append(col)
            
            if numeric_unselected:
                logger.info(f"Adding OTHERS column with sum of: {numeric_unselected}")
                # Calculate sum of unselected numeric columns (convert to numeric, treating NaN as 0)
                others_sum = pd.Series(0, index=df.index)
                for col in numeric_unselected:
                    others_sum += pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                filtered_df['OTHERS'] = others_sum.astype(int)
                others_columns = numeric_unselected

        # Apply output header overrides (display names) AFTER selecting data by original headers
        header_overrides = header_overrides or {}
        output_headers: List[str] = []
        used: Dict[str, int] = {}

        for col_name in filtered_df.columns.tolist():
            desired = header_overrides.get(col_name, col_name)
            desired = str(desired).strip() if desired is not None else str(col_name).strip()
            if not desired:
                desired = str(col_name).strip() or "Column"

            # Ensure uniqueness in Excel header row
            count = used.get(desired, 0) + 1
            used[desired] = count
            if count > 1:
                desired = f"{desired} ({count})"
            output_headers.append(desired)

        filtered_df.columns = output_headers

        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_filename = f"filtered_{timestamp}.xlsx"
        output_path = Path(output_dir) / output_filename

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Writing filtered Excel to: {output_path}")

        # Write to Excel using openpyxl for formatting control
        filtered_df.to_excel(output_path, index=False, engine='openpyxl')

        # Apply professional formatting
        self._apply_formatting(str(output_path), output_headers)

        # Prepare metadata
        metadata = {
            "original_file": input_file,
            "filtered_file": str(output_path),
            "timestamp": timestamp,
            "original_columns": available_columns,
            "selected_columns": requested_columns,
            "output_headers": output_headers,
            "total_columns": len(filtered_df.columns),
            "total_rows": len(filtered_df),
            "columns_removed": len(available_columns) - len(requested_columns),
            "include_others": include_others,
            "others_columns": others_columns if include_others else [],
        }

        logger.info(f"Filtering complete: {len(requested_columns)} columns, {len(filtered_df)} rows")

        return str(output_path), metadata

    def _apply_formatting(self, excel_file: str, column_names: List[str]):
        """
        Apply professional formatting to the filtered Excel file.

        Args:
            excel_file: Path to the Excel file to format
            column_names: List of column names (for column width calculation)
        """
        logger.info(f"Applying formatting to: {excel_file}")

        wb = openpyxl.load_workbook(excel_file)
        ws = wb.active

        # Header row styling
        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(color="FFFFFF", bold=True, size=11)
        header_alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

        # Border styling
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )

        # Apply header formatting
        for col_idx, col_name in enumerate(column_names, start=1):
            cell = ws.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_alignment
            cell.border = thin_border

            # Set column width based on content
            max_length = len(str(col_name))
            # Check data rows for longer content (sample first 100 rows)
            for row_idx in range(2, min(102, ws.max_row + 1)):
                cell_value = ws.cell(row=row_idx, column=col_idx).value
                if cell_value:
                    max_length = max(max_length, len(str(cell_value)))

            # Set column width (min 15, max 50 characters)
            adjusted_width = min(50, max(15, max_length + 2))
            ws.column_dimensions[openpyxl.utils.get_column_letter(col_idx)].width = adjusted_width

        # Set header row height
        ws.row_dimensions[1].height = 70

        # Apply data row formatting
        data_alignment = Alignment(horizontal="left", vertical="center")
        for row_idx in range(2, ws.max_row + 1):
            ws.row_dimensions[row_idx].height = 18
            for col_idx in range(1, len(column_names) + 1):
                cell = ws.cell(row=row_idx, column=col_idx)
                cell.border = thin_border
                cell.alignment = data_alignment

        # Freeze header row
        ws.freeze_panes = "A2"

        # Save formatted workbook
        wb.save(excel_file)
        wb.close()

        logger.info("Formatting applied successfully")
