#!/usr/bin/env python3
"""
PDF to JPEG Converter - Convert multi-page PDFs into individual JPEG files.
Each page becomes a separate JPEG file named as {basename}_{page_number}.jpg
Default: 300 DPI (print quality)
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Tuple, Dict
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_dependencies():
    """Verify required packages are installed."""
    required = ['pdf2image', 'PIL', 'PyPDF2']
    missing = []
    
    for package in required:
        try:
            if package == 'PIL':
                import PIL
            elif package == 'PyPDF2':
                import PyPDF2
            else:
                __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        logger.error(f"Missing dependencies: {', '.join(missing)}")
        logger.info("Install with: pip install pdf2image pillow PyPDF2 poppler-utils")
        return False
    return True


def get_pdf_page_count(pdf_path: str) -> int:
    """Get total page count from PDF file."""
    try:
        from PyPDF2 import PdfReader
        with open(pdf_path, 'rb') as f:
            reader = PdfReader(f)
            return len(reader.pages)
    except Exception as e:
        logger.error(f"Failed to read PDF page count: {e}")
        raise


def convert_pdf_to_jpeg(
    pdf_path: str,
    output_dir: str = None,
    dpi: int = 300
) -> Dict[str, any]:
    """
    Convert multi-page PDF to individual JPEG files.
    
    Args:
        pdf_path: Path to input PDF file
        output_dir: Output directory (default: ~/Downloads)
        dpi: Resolution in DPI (default: 300)
    
    Returns:
        Dictionary with results:
        {
            'success': bool,
            'total_pages': int,
            'converted_pages': int,
            'failed_pages': List[int],
            'output_files': List[str],
            'output_dir': str,
            'message': str
        }
    """
    
    # Validate input
    pdf_path = Path(pdf_path).resolve()
    if not pdf_path.exists():
        return {
            'success': False,
            'message': f"PDF file not found: {pdf_path}"
        }
    
    if not pdf_path.suffix.lower() == '.pdf':
        return {
            'success': False,
            'message': f"File is not a PDF: {pdf_path.name}"
        }
    
    # Set output directory
    if output_dir is None:
        output_dir = Path.home() / 'Downloads'  # ~/Downloads/
    else:
        output_dir = Path(output_dir).resolve()
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Get page count
        logger.info(f"Reading PDF: {pdf_path.name}")
        total_pages = get_pdf_page_count(str(pdf_path))
        logger.info(f"Total pages: {total_pages}")
        
        # Convert pages
        from pdf2image import convert_from_path
        from PIL import Image
        
        logger.info(f"Converting PDF to JPEG at {dpi} DPI...")
        
        try:
            # Convert all pages at once
            images = convert_from_path(str(pdf_path), dpi=dpi)
        except Exception as e:
            logger.error(f"Failed to convert PDF: {e}")
            raise
        
        # Save individual JPEG files
        output_files = []
        failed_pages = []
        base_name = pdf_path.stem  # filename without extension
        
        for page_num, image in enumerate(images, start=1):
            try:
                # Filename format: {basename}_{page_number:03d}.jpg
                output_file = output_dir / f"{base_name}_{page_num:03d}.jpg"
                
                # Convert RGBA to RGB if necessary (JPEG doesn't support alpha)
                if image.mode in ('RGBA', 'LA', 'P'):
                    # Create white background
                    rgb_image = Image.new('RGB', image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
                    image = rgb_image
                
                # Save as JPEG with good quality
                image.save(str(output_file), 'JPEG', quality=95)
                output_files.append(str(output_file))
                logger.info(f"✓ Page {page_num:3d}/{total_pages} → {output_file.name}")
                
            except Exception as e:
                logger.warning(f"✗ Page {page_num} failed: {e}")
                failed_pages.append(page_num)
        
        # Build result
        converted_count = len(output_files)
        success = len(failed_pages) == 0
        
        if success:
            message = f"✓ Successfully converted all {total_pages} pages to JPEG"
        else:
            message = f"⚠ Converted {converted_count} of {total_pages} pages. Failed pages: {failed_pages}"
        
        logger.info(message)
        
        return {
            'success': success,
            'total_pages': total_pages,
            'converted_pages': converted_count,
            'failed_pages': failed_pages,
            'output_files': output_files,
            'output_dir': str(output_dir),
            'message': message
        }
    
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        return {
            'success': False,
            'message': f"Conversion failed: {e}"
        }


def main():
    parser = argparse.ArgumentParser(
        description='Convert multi-page PDF to individual JPEG files'
    )
    parser.add_argument('pdf_path', help='Path to input PDF file')
    parser.add_argument(
        '-o', '--output',
        help='Output directory (default: ~/Downloads)',
        default=None
    )
    parser.add_argument(
        '-d', '--dpi',
        type=int,
        default=300,
        help='DPI resolution (default: 300 - print quality)'
    )
    
    args = parser.parse_args()
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    # Convert
    result = convert_pdf_to_jpeg(args.pdf_path, args.output, args.dpi)
    
    # Print results
    print("\n" + "="*60)
    print("CONVERSION RESULT")
    print("="*60)
    print(f"Status: {'SUCCESS' if result.get('success') else 'FAILED'}")
    if 'total_pages' in result:
        print(f"Total pages: {result['total_pages']}")
        print(f"Converted: {result['converted_pages']}")
        if result.get('failed_pages'):
            print(f"Failed pages: {result['failed_pages']}")
    print(f"Output directory: {result.get('output_dir', 'N/A')}")
    print(f"Message: {result['message']}")
    print("="*60 + "\n")
    
    # List output files if successful
    if result.get('output_files'):
        print("Generated files:")
        for file in sorted(result['output_files']):
            print(f"  - {Path(file).name}")
        print()
    
    sys.exit(0 if result.get('success') else 1)


if __name__ == '__main__':
    main()
