#!/usr/bin/env python3
"""
PDF and Image Text Extraction and OCR Module

This module provides functionality to extract text from:
1. PDF files: Direct text (PyMuPDF) or OCR for scanned PDFs
2. Image files: OCR via Tesseract (PNG, JPEG, etc.)

Supports English and Arabic text extraction.

Requirements:
- pip install pymupdf pytesseract pillow pdf2image
- Tesseract OCR: brew install tesseract (macOS) / apt install tesseract-ocr tesseract-ocr-ara (Ubuntu)

Author: SecureDoc AI Team
"""

import os
import io
from typing import Dict, Tuple, Optional, List
from pathlib import Path

# Try to import required libraries
try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False
    print("Warning: PyMuPDF not installed. Run: pip install pymupdf")

try:
    import pytesseract
    from PIL import Image
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    print("Warning: pytesseract/PIL not installed. Run: pip install pytesseract pillow")

try:
    from pdf2image import convert_from_path, convert_from_bytes
    PDF2IMAGE_AVAILABLE = True
except ImportError:
    PDF2IMAGE_AVAILABLE = False
    print("Warning: pdf2image not installed. Run: pip install pdf2image")

try:
    from src.qwen_ocr import ocr_image_bytes as _qwen_ocr_image_bytes, is_available as _qwen_is_available
    QWEN_OCR_AVAILABLE = _qwen_is_available()
except ImportError:
    try:
        from qwen_ocr import ocr_image_bytes as _qwen_ocr_image_bytes, is_available as _qwen_is_available
        QWEN_OCR_AVAILABLE = _qwen_is_available()
    except ImportError:
        QWEN_OCR_AVAILABLE = False
        _qwen_ocr_image_bytes = None
        _qwen_is_available = None


class PDFExtractor:
    """
    Extract text from PDF files using multiple methods.

    Methods:
    1. Direct text extraction (for text-based PDFs)
    2. OCR extraction (for scanned PDFs)
    """

    # Common Tesseract paths for different systems
    TESSERACT_PATHS = [
        '/opt/homebrew/opt/tesseract/bin/tesseract',  # macOS Homebrew (Apple Silicon)
        '/usr/local/bin/tesseract',                    # macOS Homebrew (Intel)
        '/usr/bin/tesseract',                          # Linux
        'tesseract',                                   # System PATH
    ]

    def __init__(self, tesseract_path: Optional[str] = None):
        """
        Initialize PDF extractor.

        Args:
            tesseract_path: Path to tesseract executable (optional, auto-detected if not provided)
        """
        self.tesseract_path = tesseract_path

        # Auto-detect Tesseract path if not provided
        if not tesseract_path and TESSERACT_AVAILABLE:
            for path in self.TESSERACT_PATHS:
                if os.path.exists(path) or path == 'tesseract':
                    try:
                        pytesseract.pytesseract.tesseract_cmd = path
                        pytesseract.get_tesseract_version()
                        self.tesseract_path = path
                        break
                    except Exception:
                        continue

        if self.tesseract_path and TESSERACT_AVAILABLE:
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path

        # Check Tesseract installation
        self.tesseract_installed = self._check_tesseract()
        self._tesseract_version = self._get_tesseract_version()

    def _get_tesseract_version(self) -> Optional[str]:
        """Get Tesseract version string if available."""
        if not TESSERACT_AVAILABLE:
            return None
        try:
            return str(pytesseract.get_tesseract_version())
        except Exception:
            return None

    def _check_tesseract(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        if not TESSERACT_AVAILABLE:
            return False
        try:
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    def extract_from_file(self, file_path: str) -> Dict:
        """
        Extract text from a PDF file.

        Args:
            file_path: Path to the PDF file

        Returns:
            Dict with:
            - text: Extracted text
            - method: Extraction method used ('text', 'ocr', 'hybrid')
            - pages: Number of pages
            - success: Whether extraction succeeded
            - error: Error message if failed
        """
        if not os.path.exists(file_path):
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': f'File not found: {file_path}'
            }

        with open(file_path, 'rb') as f:
            return self.extract_from_bytes(f.read())

    def extract_from_bytes(self, pdf_bytes: bytes) -> Dict:
        """
        Extract text from PDF bytes.

        Args:
            pdf_bytes: PDF file content as bytes

        Returns:
            Dict with extraction results
        """
        if not PYMUPDF_AVAILABLE:
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': 'PyMuPDF not installed. Run: pip install pymupdf',
                'source': 'pdf',
                'ocr_used': False,
                'pymupdf_available': False,
                'tesseract_available': self.tesseract_installed,
            }

        try:
            # Open PDF
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            num_pages = len(doc)

            # Step 1: Try direct text extraction
            text_content = []
            has_text = False

            for page_num, page in enumerate(doc):
                page_text = page.get_text("text")
                text_content.append(page_text)
                if page_text.strip():
                    has_text = True

            full_text = "\n\n".join(text_content)

            direct_text_length = len(full_text.strip())

            # If we got meaningful text, return it (with detailed metadata)
            if has_text and direct_text_length > 100:
                doc.close()
                return {
                    'text': full_text.strip(),
                    'method': 'text',
                    'pages': num_pages,
                    'success': True,
                    'error': None,
                    'source': 'pdf',
                    'ocr_used': False,
                    'direct_text_length': direct_text_length,
                    'language': 'eng+ara',
                    'dpi': None,
                    'tesseract_available': self.tesseract_installed,
                    'tesseract_version': self._tesseract_version,
                    'pdf2image_available': PDF2IMAGE_AVAILABLE,
                    'pymupdf_available': PYMUPDF_AVAILABLE,
                    'notes': 'Direct text extraction; OCR not needed.',
                }

            # Step 2: If no text or very little, try OCR
            if self.tesseract_installed and PDF2IMAGE_AVAILABLE:
                ocr_text = self._ocr_pdf_bytes(pdf_bytes)
                if ocr_text and len(ocr_text.strip()) > direct_text_length:
                    doc.close()
                    return {
                        'text': ocr_text.strip(),
                        'method': 'ocr',
                        'pages': num_pages,
                        'success': True,
                        'error': None,
                        'source': 'pdf',
                        'ocr_used': True,
                        'direct_text_length': direct_text_length,
                        'ocr_text_length': len(ocr_text.strip()),
                        'language': 'eng+ara',
                        'dpi': 200,
                        'tesseract_available': True,
                        'tesseract_version': self._tesseract_version,
                        'pdf2image_available': True,
                        'pymupdf_available': True,
                        'notes': f'Direct extraction had {direct_text_length} chars; OCR produced {len(ocr_text.strip())} chars.',
                    }

            # Step 3: Return whatever we have (with details)
            doc.close()
            return {
                'text': full_text.strip() if full_text.strip() else 'No text could be extracted',
                'method': 'text' if has_text else 'none',
                'pages': num_pages,
                'success': bool(full_text.strip()),
                'error': 'Limited text extracted, OCR not available' if not self.tesseract_installed else None,
                'source': 'pdf',
                'ocr_used': False,
                'direct_text_length': direct_text_length,
                'language': 'eng+ara',
                'dpi': None,
                'tesseract_available': self.tesseract_installed,
                'tesseract_version': self._tesseract_version,
                'pdf2image_available': PDF2IMAGE_AVAILABLE,
                'pymupdf_available': PYMUPDF_AVAILABLE,
                'notes': 'OCR was not used or did not improve extraction.' if not self.tesseract_installed else 'OCR did not yield more text than direct extraction.',
            }

        except Exception as e:
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': str(e),
                'source': 'pdf',
                'ocr_used': False,
                'tesseract_available': self.tesseract_installed,
                'pdf2image_available': PDF2IMAGE_AVAILABLE,
                'pymupdf_available': PYMUPDF_AVAILABLE,
            }

    @staticmethod
    def _prepare_grayscale(image: 'Image.Image') -> 'Image.Image':
        """Convert to grayscale and upscale if the image is small."""
        gray = image.convert('L') if image.mode != 'L' else image.copy()
        w, h = gray.size
        # Aggressively upscale small images (ID cards, passports are often small)
        if max(w, h) < 2000:
            scale = 3 if max(w, h) < 1000 else 2
            gray = gray.resize((w * scale, h * scale), Image.LANCZOS)
        return gray

    @staticmethod
    def _enhance_image(gray: 'Image.Image') -> 'Image.Image':
        """Sharpen and boost contrast without binarizing."""
        try:
            from PIL import ImageEnhance, ImageFilter
            gray = gray.filter(ImageFilter.SHARPEN)
            enhancer = ImageEnhance.Contrast(gray)
            gray = enhancer.enhance(1.8)
        except Exception:
            pass
        return gray

    @staticmethod
    def _binarize_image(gray: 'Image.Image', threshold: int = 140) -> 'Image.Image':
        """Apply binarization at a given threshold."""
        binarized = gray.point(lambda px: 255 if px > threshold else 0, '1')
        return binarized.convert('L')

    @staticmethod
    def _merge_ocr_texts(texts: List[str]) -> str:
        """
        Merge OCR results from multiple passes.
        Keeps all unique non-empty lines in order of first appearance,
        so text captured by any pass is included in the final output.
        """
        seen = set()
        merged_lines = []
        for text in texts:
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                # Normalize whitespace for dedup comparison
                key = ' '.join(stripped.split()).lower()
                if key not in seen:
                    seen.add(key)
                    merged_lines.append(stripped)
        return '\n'.join(merged_lines)

    def extract_from_image_bytes(self, image_bytes: bytes, filename: Optional[str] = None) -> Dict:
        """
        Extract text from image bytes (PNG, JPEG, etc.) using multi-pass OCR.

        Runs several OCR passes with different preprocessing and PSM modes,
        then merges all unique lines so nothing is lost (e.g. ID numbers on
        the back of national ID cards).

        Args:
            image_bytes: Raw image file content
            filename: Optional filename (used for format hint)

        Returns:
            Dict with extraction results.
        """
        # --- Try Qwen2.5-VL OCR first (higher quality, especially for Arabic) ---
        if QWEN_OCR_AVAILABLE and _qwen_ocr_image_bytes is not None:
            qwen_result = _qwen_ocr_image_bytes(image_bytes, filename=filename)
            if qwen_result.get('success') and qwen_result.get('text', '').strip():
                # Merge in standard metadata fields
                qwen_result.update({
                    'pages': 1,
                    'source': 'image',
                    'ocr_used': True,
                    'tesseract_available': self.tesseract_installed,
                    'tesseract_version': self._tesseract_version,
                    'direct_text_length': 0,
                })
                return qwen_result

        if not TESSERACT_AVAILABLE or not self.tesseract_installed:
            return {
                'text': '',
                'method': 'none',
                'pages': 1,
                'success': False,
                'error': 'Tesseract OCR not installed or not available.',
                'source': 'image',
                'ocr_used': False,
                'tesseract_available': self.tesseract_installed,
                'tesseract_version': self._tesseract_version,
                'notes': 'Install Tesseract and pytesseract to process images.',
            }
        try:
            image = Image.open(io.BytesIO(image_bytes))
            original_mode = getattr(image, 'mode', None)
            original_size = list(image.size) if hasattr(image, 'size') else None

            # Convert to RGB if necessary (e.g. PNG with transparency, palette)
            if image.mode not in ('RGB', 'L'):
                image = image.convert('RGB')

            gray = self._prepare_grayscale(image)
            enhanced = self._enhance_image(gray)

            # --- Multi-pass OCR: different preprocessing × different PSM modes ---
            # Each pass may capture text that others miss (e.g. ID numbers,
            # fine-print fields, mixed Arabic/English on back of ID cards).
            pass_results: List[str] = []

            # Pass 1: Original image, fully automatic segmentation
            pass_results.append(
                (pytesseract.image_to_string(image, lang='eng+ara', config='--psm 3') or '').strip()
            )

            # Pass 2: Enhanced grayscale (no binarization), uniform block
            pass_results.append(
                (pytesseract.image_to_string(enhanced, lang='eng+ara', config='--psm 6') or '').strip()
            )

            # Pass 3: Binarized at threshold 140 (good for dark text on light bg)
            binarized_140 = self._binarize_image(enhanced, threshold=140)
            pass_results.append(
                (pytesseract.image_to_string(binarized_140, lang='eng+ara', config='--psm 6') or '').strip()
            )

            # Pass 4: Binarized at lighter threshold 110 (catches lighter / faded text)
            binarized_110 = self._binarize_image(enhanced, threshold=110)
            pass_results.append(
                (pytesseract.image_to_string(binarized_110, lang='eng+ara', config='--psm 4') or '').strip()
            )

            # Pass 5: Sparse text mode on enhanced image (finds scattered text like ID numbers)
            pass_results.append(
                (pytesseract.image_to_string(enhanced, lang='eng+ara', config='--psm 11') or '').strip()
            )

            # Pass 6: Digits-focused pass (whitelist digits only) to catch missed numbers
            digits_text = (pytesseract.image_to_string(
                enhanced, lang='eng',
                config='--psm 11 -c tessedit_char_whitelist=0123456789'
            ) or '').strip()
            # Only include digit sequences that look like ID numbers (10+ digits in a row)
            import re
            digit_sequences = re.findall(r'\d{10,}', digits_text.replace(' ', '').replace('\n', ''))
            if digit_sequences:
                pass_results.append('\n'.join(digit_sequences))

            # Merge all unique lines from every pass
            text = self._merge_ocr_texts(pass_results)
            passes_used = sum(1 for p in pass_results if p)

            return {
                'text': text if text else 'No text could be extracted from image',
                'method': 'ocr',
                'pages': 1,
                'success': bool(text),
                'error': None if text else 'OCR returned no text',
                'source': 'image',
                'ocr_used': True,
                'direct_text_length': 0,
                'ocr_text_length': len(text),
                'text_length': len(text),
                'language': 'eng+ara',
                'dpi': _dpi_value(image),
                'image_mode': original_mode,
                'image_size': original_size,
                'tesseract_available': True,
                'tesseract_version': self._tesseract_version,
                'filename': filename,
                'notes': f'Multi-pass OCR ({passes_used} passes merged). Preprocessing: upscale + enhance + multiple thresholds + sparse text + digit extraction.',
            }
        except Exception as e:
            return {
                'text': '',
                'method': 'none',
                'pages': 1,
                'success': False,
                'error': str(e),
                'source': 'image',
                'ocr_used': False,
                'tesseract_available': self.tesseract_installed,
                'tesseract_version': self._tesseract_version,
                'filename': filename,
            }

    def _ocr_pdf_bytes(self, pdf_bytes: bytes) -> str:
        """
        Perform OCR on PDF bytes.

        Tries Qwen2.5-VL first (higher quality), falls back to Tesseract.

        Args:
            pdf_bytes: PDF content as bytes

        Returns:
            Extracted text from OCR
        """
        if not PDF2IMAGE_AVAILABLE:
            return ""

        try:
            images = convert_from_bytes(pdf_bytes, dpi=200)
            text_parts = []

            for image in images:
                page_text = ""

                # Try Qwen first
                if QWEN_OCR_AVAILABLE and _qwen_ocr_image_bytes is not None:
                    try:
                        import io
                        buf = io.BytesIO()
                        image.save(buf, format="PNG")
                        result = _qwen_ocr_image_bytes(buf.getvalue())
                        if result.get('success'):
                            page_text = result.get('text', '')
                    except Exception as qe:
                        print(f"[QwenOCR] PDF page error: {qe}")

                # Fall back to Tesseract if Qwen gave nothing
                if not page_text and TESSERACT_AVAILABLE and self.tesseract_installed:
                    page_text = pytesseract.image_to_string(
                        image,
                        lang='eng+ara',
                        config='--psm 1'
                    )

                text_parts.append(page_text)

            return "\n\n".join(text_parts)

        except Exception as e:
            print(f"OCR Error: {e}")
            return ""

    def extract_with_ocr(self, file_path: str) -> Dict:
        """
        Force OCR extraction (for scanned documents).

        Args:
            file_path: Path to PDF file

        Returns:
            Dict with extraction results
        """
        if not os.path.exists(file_path):
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': f'File not found: {file_path}'
            }

        if not self.tesseract_installed:
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': 'Tesseract OCR not installed'
            }

        with open(file_path, 'rb') as f:
            pdf_bytes = f.read()

        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            num_pages = len(doc)
            doc.close()

            ocr_text = self._ocr_pdf_bytes(pdf_bytes)

            return {
                'text': ocr_text.strip() if ocr_text else 'No text extracted',
                'method': 'ocr',
                'pages': num_pages,
                'success': bool(ocr_text.strip()),
                'error': None if ocr_text else 'OCR returned no text'
            }

        except Exception as e:
            return {
                'text': '',
                'method': 'none',
                'pages': 0,
                'success': False,
                'error': str(e)
            }


def _dpi_value(image) -> Optional[int]:
    """Get a single DPI value from PIL Image (may be (x, y) tuple)."""
    if not hasattr(image, 'info'):
        return 200
    dpi = image.info.get('dpi')
    if dpi is None:
        return 200
    if isinstance(dpi, (list, tuple)) and len(dpi) >= 1:
        return int(dpi[0]) if dpi[0] else 200
    return int(dpi) if dpi else 200


# Singleton instance
_extractor = None


def get_pdf_extractor() -> PDFExtractor:
    """Get singleton PDF extractor instance."""
    global _extractor
    if _extractor is None:
        _extractor = PDFExtractor()
    return _extractor


def extract_text_from_pdf(file_path: str) -> str:
    """
    Convenience function to extract text from PDF.

    Args:
        file_path: Path to PDF file

    Returns:
        Extracted text (empty string if failed)
    """
    extractor = get_pdf_extractor()
    result = extractor.extract_from_file(file_path)
    return result['text']


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> str:
    """
    Convenience function to extract text from PDF bytes.

    Args:
        pdf_bytes: PDF content as bytes

    Returns:
        Extracted text (empty string if failed)
    """
    extractor = get_pdf_extractor()
    result = extractor.extract_from_bytes(pdf_bytes)
    return result['text']


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("PDF EXTRACTOR TEST")
    print("=" * 60)

    extractor = PDFExtractor()

    print(f"\nDependencies:")
    print(f"  PyMuPDF: {'✓' if PYMUPDF_AVAILABLE else '✗'}")
    print(f"  Tesseract: {'✓' if extractor.tesseract_installed else '✗'}")
    print(f"  pdf2image: {'✓' if PDF2IMAGE_AVAILABLE else '✗'}")

    # Test with sample PDF if available
    test_files = [
        "../Account opening agreement 2023- updated.pdf",
        "Account opening agreement 2023- updated.pdf"
    ]

    for test_file in test_files:
        if os.path.exists(test_file):
            print(f"\nTesting: {test_file}")
            result = extractor.extract_from_file(test_file)
            print(f"  Success: {result['success']}")
            print(f"  Method: {result['method']}")
            print(f"  Pages: {result['pages']}")
            print(f"  Text length: {len(result['text'])} chars")
            if result['error']:
                print(f"  Error: {result['error']}")
            print(f"  Preview: {result['text'][:200]}...")
            break
    else:
        print("\nNo test PDF found.")
