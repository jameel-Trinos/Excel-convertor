# Excel Formatting Quick Reference

**One-page guide for perfect Excel formatting in this project.**

---

## 🎯 The Golden Rules

1. **Fixed Column Widths** (15-20 chars) — NOT auto-fit
2. **Set Row Heights** (header: 70px, data: 18px)
3. **wrap_text=True** for headers ONLY
4. **Freeze header row** for scrolling
5. **Merge title cells** across all columns
6. **Borders on all cells**
7. **Validate with recalc.py** before delivery

---

## 📏 Column Widths (Fixed, Not Auto-Fit)

```python
from openpyxl.utils import get_column_letter

# Set ALL columns to 16 characters width
for col in range(1, num_columns + 1):
    col_letter = get_column_letter(col)
    worksheet.column_dimensions[col_letter].width = 16
```

**Recommended widths**: 15-20 characters (16 is perfect default)

---

## 📐 Row Heights (Critical!)

```python
# Header row (tall for wrapped text)
worksheet.row_dimensions[header_row].height = 70

# All data rows (breathing room)
for row in range(data_start_row, data_end_row + 1):
    worksheet.row_dimensions[row].height = 18

# Title row
worksheet.row_dimensions[1].height = 25
```

---

## 🎨 Cell Formatting

### Headers (Blue, White Text, Wrapped)

```python
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

cell.font = Font(bold=True, size=10, color='FFFFFF')
cell.fill = PatternFill(start_color='4472C4', end_color='4472C4', fill_type='solid')
cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
cell.border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
```

### Data Cells (White, Black Text, No Wrap)

```python
cell.font = Font(bold=False, size=10, color='000000')
cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
cell.border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
```

---

## 🧮 Formulas

### Row Total (Sum Across Columns)

```python
# Sum columns B through O for each row
cell.value = f"=SUM(B{row}:{get_column_letter(last_col)}{row})"
cell.number_format = "#,##0"
```

### Column Total (Sum Down Rows)

```python
# Sum rows 7 through 100 for each column
col_letter = get_column_letter(col)
cell.value = f"=SUM({col_letter}{data_start}:{col_letter}{data_end})"
cell.number_format = "#,##0"
```

---

## 🧊 Freeze Panes

```python
# Freeze header row (everything above row 7)
worksheet.freeze_panes = 'A7'  # Adjust row number as needed
```

---

## 📋 Title Rows (Merged)

```python
from openpyxl.utils import get_column_letter

# Merge title across ALL columns
last_col = get_column_letter(num_columns)
worksheet.merge_cells(f'A1:{last_col}1')

# Format merged cell
cell = worksheet['A1']
cell.value = 'FORM 20 - FINAL RESULT SHEET'
cell.font = Font(bold=True, size=14)
cell.alignment = Alignment(horizontal='center', vertical='center')
cell.fill = PatternFill(start_color='D9E1F2', end_color='D9E1F2', fill_type='solid')
```

---

## ✅ Quality Validation

### Using Quality Checker (Python)

```python
from app.quality_checker import check_excel_quality

passed = check_excel_quality("output.xlsx", verbose=True)
if not passed:
    print("Fix errors before delivery!")
```

### Using recalc.py (CLI)

```bash
python backend/recalc.py output.xlsx
```

**Expected output:**
```
✓ NO ERRORS - All formulas are valid!
```

---

## ⚠️ Common Mistakes

| ❌ Mistake | ✅ Solution |
|-----------|-----------|
| Using auto-fit for columns | Set fixed widths (16 chars) |
| No row heights set | Header: 70px, Data: 18px |
| Missing wrap_text on headers | `wrap_text=True` for headers |
| Wrong formula ranges | Use `get_column_letter()` dynamically |
| Title not merged | Merge across ALL columns |
| No freeze panes | Freeze header row |

---

## 🚀 Quick Implementation

### Using This Project's Built-in Tools

The project already handles all this automatically via:

**In formatter.py:**
- `set_fixed_column_widths(worksheet, default_width=16)`
- `set_row_heights(worksheet, header_row, data_start_row, data_end_row)`
- `format_header_row(worksheet, row_number)`
- `format_data_cells(worksheet, start_row, end_row)`

**In excel_creator.py:**
```python
# Already implemented:
self.formatter.set_fixed_column_widths(worksheet, default_width=16)
self.formatter.set_row_heights(worksheet, header_row, data_start_row, data_end_row)
worksheet.freeze_panes = worksheet.cell(row=header_row + 1, column=1)
```

**Just use the ExcelCreator class and it handles everything!**

---

## 📚 Full Documentation

For complete details, see: [EXCEL_FORMATTING_GUIDE.md](EXCEL_FORMATTING_GUIDE.md)

---

**Remember**: Fixed widths + Row heights + wrap_text headers = Perfect Excel files! ✨
