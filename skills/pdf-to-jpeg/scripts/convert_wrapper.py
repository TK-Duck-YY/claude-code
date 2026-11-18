#!/usr/bin/env python3
"""
Wrapper for pdf-to-jpeg skill - callable by Claude with JSON input/output.
"""

import json
import sys
from pathlib import Path

# 本檔與 pdf_to_jpeg.py 在同一個資料夾。再往下一層 scripts 會找不到模組。
sys.path.insert(0, str(Path(__file__).resolve().parent))

from pdf_to_jpeg import convert_pdf_to_jpeg, check_dependencies


def main():
    """
    Read JSON from stdin, process PDF, return JSON result.
    
    Input JSON format:
    {
        "pdf_path": "/path/to/file.pdf",
        "output_dir": "/path/to/output",  # optional, defaults to ~/Downloads
        "dpi": 300                         # optional, defaults to 300
    }
    """
    
    try:
        # Read input
        input_data = json.loads(sys.stdin.read())
        
        pdf_path = input_data.get('pdf_path')
        output_dir = input_data.get('output_dir')
        dpi = input_data.get('dpi', 300)
        
        if not pdf_path:
            result = {
                'success': False,
                'message': 'Missing required parameter: pdf_path'
            }
        else:
            # Check dependencies
            if not check_dependencies():
                result = {
                    'success': False,
                    'message': 'Missing dependencies. Install: pip install pdf2image pillow PyPDF2'
                }
            else:
                # Convert
                result = convert_pdf_to_jpeg(pdf_path, output_dir, dpi)
        
        # Output JSON result
        print(json.dumps(result, indent=2))
        sys.exit(0 if result.get('success') else 1)
    
    except json.JSONDecodeError as e:
        result = {'success': False, 'message': f'Invalid JSON input: {e}'}
        print(json.dumps(result, indent=2))
        sys.exit(1)
    except Exception as e:
        result = {'success': False, 'message': f'Error: {e}'}
        print(json.dumps(result, indent=2))
        sys.exit(1)


if __name__ == '__main__':
    main()
