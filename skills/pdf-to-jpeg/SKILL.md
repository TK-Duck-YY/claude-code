---
name: pdf-to-jpeg
description: Convert multi-page PDF files into individual JPEG images, one page per file. Trigger whenever the user mentions converting PDF pages to images, splitting a PDF into separate image files, extracting PDF pages as JPEGs for document editing or embedding, or needing page-by-page image extraction from PDF. Use this skill for any document digitization workflow, OCR preparation, or when JPEG images of PDF pages are needed for insertion into Word/Excel/other Office documents.
---

# PDF to JPEG Converter Skill

Convert continuous multi-page PDF documents into separate JPEG image files, one per page, at print quality (300 DPI) suitable for document editing and embedding.

## When to Use This Skill

- **Page extraction**: User uploads a PDF and wants individual JPEG files for each page
- **Office document embedding**: Need to insert PDF pages as images into Word/Excel/presentations
- **Document digitization**: Converting paper-scanned PDFs into editable image format
- **Image-based editing**: When JPEG format is required for downstream editing tools
- **Independent workflow**: User calls this directly, or integration point for other skills (Office-related automation)

## Workflow

### Input
- **PDF file**: Multi-page PDF document (required)
- **Output directory**: Target folder for JPEG files (optional, defaults to `~/Downloads/`)
- **DPI (optional)**: Resolution for JPEG output
  - **72**: Web/screen quality (fastest, smallest files)
  - **150**: Document editing (lower quality, fast)
  - **200**: High quality
  - **300**: Print quality (default, recommended for editing and archive)

### Process
1. Validate PDF file exists and is readable
2. Detect total page count
3. Convert each page to JPEG at specified DPI (default: 300 DPI for optimal clarity)
4. Name output files as: `{original_pdf_name}_{page_number}.jpg` (e.g., `report_001.jpg`, `report_002.jpg`)
5. Handle conversion errors gracefully:
   - If a page fails: Log the page number, skip it, continue with remaining pages
   - At end: Report which pages (if any) failed to convert
6. Return file list and summary

### Output
- JPEG files saved to specified directory
- Summary report: total pages, successful conversions, failed pages (if any)
- File paths for downstream use

## Error Handling Strategy

| Scenario | Behavior |
|----------|----------|
| PDF file missing | Abort with clear error message |
| PDF corrupted/unreadable | Report corruption, attempt partial recovery if possible |
| Single page fails | Log page number, skip, continue with next page |
| All pages fail | Abort and report |
| Insufficient disk space | Check before conversion, warn user |

## Example Usage

**User prompt:**
> "I have a 15-page PDF report. Convert each page to a separate JPEG for inserting into my Word document."

**Skill response:**
1. Validates the PDF file
2. Converts all 15 pages at 300 DPI
3. Saves as: `report_001.jpg` through `report_015.jpg`
4. Returns: "✓ Successfully converted 15 pages. Files ready in ~/Downloads/"

**Error case:**
> User uploads a damaged PDF with 20 pages

**Skill response:**
1. Converts pages 1-18 successfully
2. Pages 19-20 fail (corruption)
3. Returns: "⚠ Converted 18 of 20 pages. Failed: pages 19, 20 (corrupted). Check PDF or try re-scanning."

---

## Technical Details

### Dependencies
- `pdf2image` (PDF page rasterization)
- `Pillow` (JPEG encoding)
- `PyPDF2` (page counting, validation)

### Output Format
- **DPI**: 300 (print quality, optimal for document editing and archival)
- **Format**: JPEG (.jpg)
- **Naming**: `{basename}_{page:03d}.jpg` (zero-padded page numbers)
- **Color**: RGB (color PDFs), grayscale (B&W PDFs, auto-detected)
- **Quality**: 95% JPEG compression (high quality, reasonable file size)

### Performance
- Typical throughput: 1-2 pages/second on M1 Mac at 300 DPI
- Memory usage: Streaming per-page (not loading entire PDF into RAM)
- File size: ~287 KB per page at 300 DPI

---

## Integration Notes

### Called Independently
```
User: "Convert my PDF to JPEG pages"
→ Skill triggers, processes PDF at 300 DPI, returns file list
```

### Called by Office Automation Skills
When Office-related skills (e.g., future `docx-image-embed`) need to insert PDF pages as images:
```
presentation-generator → [needs PDF as images] → pdf-to-jpeg → returns JPEG paths
docx-image-embed → [needs to embed PDF pages] → pdf-to-jpeg → returns JPEG paths
```

### Output Integration
Returned file paths can be directly passed to:
- Word document embedding
- Excel cell image insertion
- PowerPoint slide graphics
- Any image processing workflow

---

## FAQ

**Q: Why 300 DPI as default?**  
A: 300 DPI is print quality and provides excellent clarity for document editing. When you insert these JPEGs into Word or other documents, text will be crisp and readable. For web or screen-only viewing, you can specify 72 or 150 DPI for faster conversion and smaller files.

**Q: What if I only want certain pages?**  
A: Current version converts all pages. For selective extraction, use this skill first, then delete unwanted JPEGs.

**Q: Can I specify output filename pattern?**  
A: Current version uses `{basename}_{page:03d}.jpg`. Custom patterns can be added in v2.

**Q: What about color vs. B&W?**  
A: Auto-detected. Color PDFs → RGB JPEGs. B&W PDFs → grayscale. No manual override needed.

---

## Changelog

- **v1.1** (June 2026): Changed default DPI from 150 to 300 for better print quality
- **v1.0** (June 2026): Initial release. Multi-page PDF → individual JPEG conversion, graceful error handling, file naming with zero-padded page numbers.
