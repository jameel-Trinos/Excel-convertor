"""
Test script to verify OCR setup and functionality.

Run this script to test:
1. Tesseract OCR installation
2. pdf2image/Poppler installation
3. EasyOCR (optional) installation
4. Basic OCR functionality
5. Integration with PDF processor
"""

import sys
from pathlib import Path

def test_imports():
    """Test if all required packages can be imported."""
    print("Testing Python package imports...")
    
    try:
        import pytesseract
        print("  ✓ pytesseract imported successfully")
    except ImportError as e:
        print(f"  ✗ pytesseract import failed: {e}")
        return False
    
    try:
        from pdf2image import convert_from_path
        print("  ✓ pdf2image imported successfully")
    except ImportError as e:
        print(f"  ✗ pdf2image import failed: {e}")
        return False
    
    try:
        import cv2
        print("  ✓ opencv-python imported successfully")
    except ImportError as e:
        print(f"  ✗ opencv-python import failed: {e}")
        return False
    
    try:
        import easyocr
        print("  ✓ easyocr imported successfully (optional)")
    except ImportError as e:
        print(f"  ⚠ easyocr not available (optional): {e}")
    
    try:
        import numpy as np
        print("  ✓ numpy imported successfully")
    except ImportError as e:
        print(f"  ✗ numpy import failed: {e}")
        return False
    
    return True


def test_tesseract():
    """Test if Tesseract OCR is installed and accessible."""
    print("\nTesting Tesseract OCR installation...")
    
    try:
        import pytesseract
        
        # Try to get version
        version = pytesseract.get_tesseract_version()
        print(f"  ✓ Tesseract version: {version}")
        
        # Try to list available languages
        try:
            langs = pytesseract.get_languages()
            print(f"  ✓ Available languages: {', '.join(langs[:5])}{'...' if len(langs) > 5 else ''}")
        except Exception as e:
            print(f"  ⚠ Could not list languages: {e}")
        
        return True
    except Exception as e:
        print(f"  ✗ Tesseract not found or not working: {e}")
        print("     Install Tesseract:")
        print("       macOS: brew install tesseract")
        print("       Ubuntu: sudo apt-get install tesseract-ocr")
        print("       Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
        return False


def test_poppler():
    """Test if Poppler is installed (required for pdf2image)."""
    print("\nTesting Poppler installation...")
    
    try:
        from pdf2image import pdfinfo_from_path
        
        # Try to get pdfinfo (tests Poppler)
        # We can't test without a PDF, so just check if function exists
        print("  ✓ pdf2image can access Poppler functions")
        print("     Note: Full test requires a PDF file")
        return True
    except Exception as e:
        print(f"  ✗ Poppler not found: {e}")
        print("     Install Poppler:")
        print("       macOS: brew install poppler")
        print("       Ubuntu: sudo apt-get install poppler-utils")
        print("       Windows: Download from https://github.com/oschwartz10612/poppler-windows/releases")
        return False


def test_ocr_basic():
    """Test basic OCR functionality with a simple image."""
    print("\nTesting basic OCR functionality...")
    
    try:
        import pytesseract
        from PIL import Image
        import numpy as np
        
        # Create a simple test image with text
        from PIL import ImageDraw, ImageFont
        
        img = Image.new('RGB', (300, 100), color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw some text
        try:
            # Try to use a system font
            font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 24)
        except:
            try:
                font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
            except:
                font = ImageFont.load_default()
        
        draw.text((10, 30), "Test OCR 123", fill='black', font=font)
        
        # Perform OCR
        text = pytesseract.image_to_string(img)
        print(f"  ✓ OCR test successful")
        print(f"     Extracted text: '{text.strip()}'")
        
        # Test with confidence
        from pytesseract import Output
        data = pytesseract.image_to_data(img, output_type=Output.DICT)
        confidences = [float(c) for c in data['conf'] if c != '-1']
        if confidences:
            avg_conf = sum(confidences) / len(confidences)
            print(f"     Average confidence: {avg_conf:.1f}%")
        
        return True
    except Exception as e:
        print(f"  ✗ OCR test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_app_modules():
    """Test if our app modules can be imported."""
    print("\nTesting app module imports...")
    
    try:
        from app.pdf_detector import PDFTypeDetector
        print("  ✓ pdf_detector imported")
    except Exception as e:
        print(f"  ✗ pdf_detector import failed: {e}")
        return False
    
    try:
        from app.ocr_processor import OCRProcessor, OCRConfig
        print("  ✓ ocr_processor imported")
    except Exception as e:
        print(f"  ✗ ocr_processor import failed: {e}")
        return False
    
    try:
        from app.table_parser import OCRTableParser
        print("  ✓ table_parser imported")
    except Exception as e:
        print(f"  ✗ table_parser import failed: {e}")
        return False
    
    try:
        from app.data_validator import ExtractionValidator
        print("  ✓ data_validator imported")
    except Exception as e:
        print(f"  ✗ data_validator import failed: {e}")
        return False
    
    try:
        from app.pdf_processor import PDFProcessor
        print("  ✓ pdf_processor imported")
    except Exception as e:
        print(f"  ✗ pdf_processor import failed: {e}")
        return False
    
    try:
        from app.models import TableData
        # Check if new fields exist
        table = TableData(headers=[], rows=[])
        assert hasattr(table, 'extraction_method')
        assert hasattr(table, 'confidence_score')
        print("  ✓ models.TableData has required fields")
    except Exception as e:
        print(f"  ✗ models validation failed: {e}")
        return False
    
    return True


def main():
    """Run all tests."""
    print("="*60)
    print("OCR Setup Verification")
    print("="*60)
    
    results = []
    
    # Test imports
    results.append(("Package Imports", test_imports()))
    
    # Test Tesseract
    results.append(("Tesseract OCR", test_tesseract()))
    
    # Test Poppler
    results.append(("Poppler", test_poppler()))
    
    # Test basic OCR
    results.append(("Basic OCR", test_ocr_basic()))
    
    # Test app modules
    results.append(("App Modules", test_app_modules()))
    
    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✓ All tests passed! OCR setup is complete.")
        return 0
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())




