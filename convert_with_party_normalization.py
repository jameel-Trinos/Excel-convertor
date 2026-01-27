#!/usr/bin/env python3
"""
PDF to Excel Converter with Party Name Normalization

This script demonstrates the complete workflow:
1. Extract data from PDF using Anthropic Claude AI
2. Normalize political party column names
3. Aggregate minor parties into "OTHERS" category
4. Create a formatted Excel file

Usage:
    python convert_with_party_normalization.py <pdf_file>

Requirements:
    - ANTHROPIC_API_KEY environment variable must be set
    - PDF should contain election data with party vote columns
"""

import asyncio
import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from app.enhanced_claude_processor import EnhancedClaudeProcessor
from app.party_normalizer import PartyNormalizer
from app.excel_creator import ExcelCreator


async def convert_pdf_with_party_normalization(pdf_path: str, output_path: str = None):
    """
    Convert PDF to Excel with party name normalization.
    
    Args:
        pdf_path: Path to input PDF file
        output_path: Path for output Excel file (optional)
    
    Returns:
        Path to created Excel file
    """
    # Validate input
    if not os.path.exists(pdf_path):
        print(f"❌ Error: PDF file not found: {pdf_path}")
        return None
    
    # Check for API key
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        print("   Please set it using: export ANTHROPIC_API_KEY='your-api-key'")
        return None
    
    # Generate output path if not provided
    if not output_path:
        pdf_stem = Path(pdf_path).stem
        output_path = f"{pdf_stem}_normalized.xlsx"
    
    print("=" * 80)
    print("PDF TO EXCEL CONVERTER WITH PARTY NORMALIZATION")
    print("=" * 80)
    print(f"Input PDF: {pdf_path}")
    print(f"Output Excel: {output_path}")
    print()
    
    # Step 1: Extract data using Claude AI
    print("📄 Step 1: Extracting data from PDF using Claude AI...")
    print("-" * 80)
    
    processor = EnhancedClaudeProcessor(api_key=api_key)
    
    def progress_callback(progress: int, message: str):
        print(f"   [{progress:3d}%] {message}")
    
    try:
        # Enhanced extraction with party normalization enabled
        tables, metadata = await processor.enhanced_extract(
            pdf_path,
            progress_callback=progress_callback,
            apply_party_normalization=True  # Enable party normalization
        )
        
        if not tables:
            print("❌ Error: No tables found in PDF")
            return None
        
        print(f"✅ Extracted {len(tables)} table(s) with {sum(len(t.rows) for t in tables)} total rows")
        print()
        
        # Display Claude's analysis
        if metadata.get("document_title"):
            print(f"📋 Document Title: {metadata['document_title']}")
        
        print(f"📊 Tables Processed: {metadata.get('tables_processed', len(tables))}")
        print(f"📈 Total Rows: {metadata.get('total_rows', 0)}")
        
        if metadata.get("party_normalization_applied"):
            print(f"✅ Party normalization: Applied")
        print()
        
    except Exception as e:
        print(f"❌ Error during extraction: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Step 2: Display normalized columns
    print("🎯 Step 2: Party Column Normalization Applied")
    print("-" * 80)
    
    # Get headers from first table (already normalized)
    normalized_headers = tables[0].headers if tables else []
    print(f"Final normalized headers ({len(normalized_headers)} columns):")
    for i, header in enumerate(normalized_headers, 1):
        print(f"   {i}. {header}")
    print()
    
    # Combine all data rows from all tables
    all_data_rows = []
    for table in tables:
        all_data_rows.extend(table.rows)
    
    print(f"✅ Party normalization complete:")
    print(f"   • Final columns: {len(normalized_headers)}")
    print(f"   • Total rows: {len(all_data_rows)}")
    print()
    
    # Step 3: Create Excel file
    print("📊 Step 3: Creating Excel file...")
    print("-" * 80)
    
    try:
        # Create Excel with normalized data
        creator = ExcelCreator(ai_processor=None)  # No additional AI processing needed
        
        await asyncio.to_thread(
            creator.create_from_tables,
            tables,
            output_path,
            source_filename=os.path.basename(pdf_path),
            page_texts=[],
            document_title=metadata.get("document_title", "")
        )
        
        print(f"✅ Excel file created successfully: {output_path}")
        
        # Display file info
        file_size = os.path.getsize(output_path)
        print(f"   • File size: {file_size:,} bytes ({file_size / 1024:.1f} KB)")
        print()
        
    except Exception as e:
        print(f"❌ Error creating Excel: {e}")
        import traceback
        traceback.print_exc()
        return None
    
    # Step 4: Summary
    print("=" * 80)
    print("✅ CONVERSION COMPLETE")
    print("=" * 80)
    print()
    print("Party Normalization Summary:")
    print("  • DMK columns → DMK")
    print("  • AIADMK columns → AIADMK")
    print("  • BJP columns → BJP")
    print("  • Congress columns → CONGRESS")
    print("  • VCK columns → VCK")
    print("  • PMK columns → PMK")
    print("  • NTK columns → NTK")
    print("  • All other parties → OTHERS (aggregated)")
    print()
    print(f"📂 Output file: {output_path}")
    print()
    
    return output_path


async def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python convert_with_party_normalization.py <pdf_file> [output_excel]")
        print()
        print("Example:")
        print("  python convert_with_party_normalization.py election_data.pdf")
        print("  python convert_with_party_normalization.py election_data.pdf output.xlsx")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    result = await convert_pdf_with_party_normalization(pdf_path, output_path)
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

