"""Debug script to test constituency text parser and see what's being extracted."""

import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.constituency_text_parser import ConstituencyTextParser

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def debug_parse(pdf_path: str):
    """Debug the parsing process step by step."""
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        print(f"ERROR: PDF file not found: {pdf_path}")
        return
    
    print(f"\n{'='*80}")
    print(f"DEBUGGING CONSTITUENCY TEXT PARSER")
    print(f"{'='*80}")
    print(f"PDF: {pdf_path}\n")
    
    try:
        parser = ConstituencyTextParser(str(pdf_path))
        
        # Step 1: Extract raw text
        print("\n[STEP 1] Extracting text from PDF...")
        all_lines = parser._extract_text_from_pdf()
        print(f"Extracted {len(all_lines)} lines")
        print("\nFirst 20 lines:")
        for i, line in enumerate(all_lines[:20], 1):
            print(f"  {i:2d}: {line[:100]}")
        
        # Step 2: Filter headers/footers
        print("\n[STEP 2] Filtering headers and footers...")
        filtered_lines = parser._filter_headers_footers(all_lines)
        print(f"Filtered to {len(filtered_lines)} lines")
        print("\nFirst 20 filtered lines:")
        for i, line in enumerate(filtered_lines[:20], 1):
            print(f"  {i:2d}: {line[:100]}")
        
        # Step 3: Parse entries
        print("\n[STEP 3] Parsing entries...")
        entries = parser._parse_entries(filtered_lines)
        print(f"Parsed {len(entries)} entries\n")
        
        # Step 4: Display results
        print("\n[STEP 4] Parsed Entries:")
        print("="*80)
        for i, entry in enumerate(entries, 1):
            print(f"\nEntry {i}:")
            print(f"  Serial No: {entry['serial_no']}")
            print(f"  ID No: {entry['id_no']}")
            print(f"  Location: {entry['location']}")
            print(f"  Areas: {entry['areas']}")
        
        # Step 5: Show as table format
        print("\n[STEP 5] Table Format:")
        print("="*80)
        print(f"{'Sl.No':<8} {'ID':<8} {'Location':<50} {'Areas':<50}")
        print("-"*120)
        for entry in entries:
            location = entry['location'][:47] + "..." if len(entry['location']) > 50 else entry['location']
            areas = entry['areas'][:47] + "..." if len(entry['areas']) > 50 else entry['areas']
            print(f"{entry['serial_no']:<8} {entry['id_no']:<8} {location:<50} {areas:<50}")
        
        print(f"\n{'='*80}")
        print(f"SUMMARY: {len(entries)} entries extracted successfully")
        print(f"{'='*80}\n")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python debug_constituency_parser.py <pdf_path>")
        print("\nExample:")
        print("  python debug_constituency_parser.py AC001.pdf")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    debug_parse(pdf_path)



