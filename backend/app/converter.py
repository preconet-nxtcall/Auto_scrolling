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
        
    # 3. Office, CSV & HTML
    if ext in (".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv", ".html", ".htm"):
        return convert_office_via_libreoffice(input_path, output_pdf_path)
        
    return False, 0, f"Unsupported file extension: {ext}"
