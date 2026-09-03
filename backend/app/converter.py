import os
import shutil
import subprocess
import logging
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from app.config import settings

logger = logging.getLogger("uvicorn.error")

def count_pdf_pages(pdf_path: Path) -> int:
    """Returns page count of a PDF file using PyPDF."""
    try:
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception as e:
        logger.warning(f"Error reading PDF page count for {pdf_path}: {e}")
        return 1

def convert_image_to_pdf(image_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """Converts image formats (.png, .jpg, .jpeg, .webp, .tiff) to PDF using Pillow."""
    try:
        with Image.open(image_path) as img:
            # Convert image mode to RGB if necessary (e.g. RGBA pngs)
            if img.mode in ("RGBA", "P", "LA"):
                img = img.convert("RGB")
            img.save(str(output_pdf_path), "PDF", resolution=100.0)
        return True, 1, ""
    except Exception as e:
        err_msg = f"Image conversion failed: {str(e)}"
        logger.error(err_msg)
        return False, 0, err_msg

def convert_office_via_libreoffice(input_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """Converts Word, Excel, PowerPoint, CSV files to PDF using headless LibreOffice."""
    output_dir = output_pdf_path.parent
    
    # Check for soffice or libreoffice executables
    executables = ["soffice", "libreoffice"]
    # Check common Windows paths for LibreOffice
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    ]
    
    cmd_binary = None
    for path in win_paths:
        if os.path.exists(path):
            cmd_binary = path
            break
            
    if not cmd_binary:
        for exe in executables:
            if shutil.which(exe):
                cmd_binary = exe
                break
                
    if not cmd_binary:
        err_msg = (
            "LibreOffice is not installed or not in system PATH. "
            "Please install LibreOffice to convert Word, Excel, PowerPoint, and CSV files."
        )
        logger.warning(err_msg)
        return False, 0, err_msg

    try:
        cmd = [
            cmd_binary,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(input_path)
        ]
        logger.info(f"Running LibreOffice conversion command: {' '.join(cmd)}")
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=60)
        
        if result.returncode != 0:
            err_msg = f"LibreOffice conversion failed with exit code {result.returncode}: {result.stderr}"
            logger.error(err_msg)
            return False, 0, err_msg

        # LibreOffice outputs a PDF with the input filename stem
        expected_output = output_dir / f"{input_path.stem}.pdf"
        if expected_output.exists():
            if expected_output != output_pdf_path:
                shutil.move(str(expected_output), str(output_pdf_path))
            pages = count_pdf_pages(output_pdf_path)
            return True, pages, ""
        else:
            err_msg = f"LibreOffice completed but output file '{expected_output.name}' was not found."
            logger.error(err_msg)
            return False, 0, err_msg

    except subprocess.TimeoutExpired:
        err_msg = "LibreOffice conversion timed out after 60 seconds."
        logger.error(err_msg)
        return False, 0, err_msg
    except Exception as e:
        err_msg = f"LibreOffice conversion exception: {str(e)}"
        logger.error(err_msg)
        return False, 0, err_msg

def convert_html_to_pdf(input_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """
    Converts HTML (.html, .htm) files to vector PDF.
    1. First attempts headless LibreOffice conversion.
    2. If LibreOffice fails, is missing, or times out, uses ReportLab flowables to render HTML into a clean PDF.
    """
    success, pages, err = convert_office_via_libreoffice(input_path, output_pdf_path)
    if success and output_pdf_path.exists() and output_pdf_path.stat().st_size > 0:
        return True, pages, ""

    logger.info(f"LibreOffice HTML conversion notice: {err}. Attempting ReportLab fallback HTML converter.")

    try:
        import re
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib import colors
        from html.parser import HTMLParser

        html_content = input_path.read_text(encoding="utf-8", errors="replace")
        clean_html = re.sub(r'<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>', '', html_content, flags=re.IGNORECASE)

        class HTMLToFlowablesParser(HTMLParser):
            def __init__(self):
                super().__init__()
                self.flowables = []
                self.styles = getSampleStyleSheet()
                self.current_tag = None
                self.current_text = []

            def handle_starttag(self, tag, attrs):
                self.flush_text()
                self.current_tag = tag.lower()

            def handle_endtag(self, tag):
                self.flush_text()
                self.current_tag = None

            def handle_data(self, data):
                text = data.strip()
                if text:
                    self.current_text.append(data)

            def flush_text(self):
                if not self.current_text:
                    return
                text = "".join(self.current_text).strip()
                self.current_text = []
                if not text:
                    return

                safe_text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

                if self.current_tag in ("h1", "h2", "h3"):
                    style = ParagraphStyle(
                        'Heading',
                        parent=self.styles['Heading1'],
                        fontSize=18 if self.current_tag == "h1" else 14,
                        leading=22 if self.current_tag == "h1" else 18,
                        textColor=colors.HexColor('#1e293b'),
                        spaceAfter=8
                    )
                    self.flowables.append(Paragraph(safe_text, style))
                    self.flowables.append(Spacer(1, 6))
                else:
                    style = ParagraphStyle(
                        'Body',
                        parent=self.styles['Normal'],
                        fontSize=10,
                        leading=14,
                        textColor=colors.HexColor('#334155'),
                        spaceAfter=6
                    )
                    self.flowables.append(Paragraph(safe_text, style))

        doc_pdf = SimpleDocTemplate(
            str(output_pdf_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )

        parser = HTMLToFlowablesParser()
        parser.feed(clean_html)
        parser.flush_text()

        if not parser.flowables:
            styles = getSampleStyleSheet()
            plain_text = re.sub(r'<[^>]+>', ' ', html_content).strip()
            if not plain_text:
                plain_text = f"HTML Document: {input_path.stem}"
            safe_plain = plain_text[:2000].replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            parser.flowables.append(Paragraph(safe_plain, styles['Normal']))

        doc_pdf.build(parser.flowables)
        pages = count_pdf_pages(output_pdf_path)
        return True, max(1, pages), ""

    except Exception as e:
        err_msg = f"HTML to PDF conversion failed: {str(e)}"
        logger.error(err_msg)
        return False, 0, err_msg


def process_document_conversion(input_path: Path, output_pdf_path: Path, file_ext: str) -> tuple[bool, int, str]:
    """Unified document conversion dispatcher."""
    ext = file_ext.lower()
    
    # 1. Native PDF
    if ext == ".pdf":
        try:
            shutil.copy(str(input_path), str(output_pdf_path))
            pages = count_pdf_pages(output_pdf_path)
            return True, pages, ""
        except Exception as e:
            return False, 0, f"Failed to process PDF: {str(e)}"
            
    # 2. Images
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff"):
        return convert_image_to_pdf(input_path, output_pdf_path)

    # 3. HTML Files
    if ext in (".html", ".htm"):
        return convert_html_to_pdf(input_path, output_pdf_path)
        
    # 4. Office & CSV
    if ext in (".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv"):
        return convert_office_via_libreoffice(input_path, output_pdf_path)
        
    return False, 0, f"Unsupported file extension: {ext}"
