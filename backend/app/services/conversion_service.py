import os
import csv
import shutil
import subprocess
import logging
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors
from app.config import settings
from app.database import SessionLocal
from app.models import Document

logger = logging.getLogger("uvicorn.error")

def count_pdf_pages(pdf_path: Path) -> int:
    """Returns page count of a PDF file using PyPDF."""
    try:
        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except Exception as e:
        logger.warning(f"Error reading PDF page count for '{pdf_path.name}': {e}")
        return 1

def convert_image_to_pdf(input_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """Converts image formats (.png, .jpg, .jpeg, .webp, .tiff, .bmp, .gif) to PDF using Pillow."""
    try:
        with Image.open(input_path) as img:
            # Handle multi-frame images (e.g. animated GIFs or multi-page TIFFs)
            frames = []
            if getattr(img, "is_animated", False):
                for frame_idx in range(img.n_frames):
                    img.seek(frame_idx)
                    frame_rgb = img.convert("RGB")
                    frames.append(frame_rgb)
            else:
                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")
                frames.append(img.convert("RGB"))

            if len(frames) > 1:
                frames[0].save(str(output_pdf_path), "PDF", save_all=True, append_images=frames[1:], resolution=100.0)
            else:
                frames[0].save(str(output_pdf_path), "PDF", resolution=100.0)

            pages = count_pdf_pages(output_pdf_path)
            return True, pages, ""
    except Exception as e:
        err_msg = f"Image conversion failed: {str(e)}"
        logger.error(f"[Conversion Error] {err_msg}")
        return False, 0, err_msg

def convert_csv_via_reportlab(input_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """Converts CSV file to PDF using ReportLab as a server-side fallback."""
    try:
        data = []
        with open(input_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f)
            for row in reader:
                if row:
                    data.append([cell.strip() for cell in row])
        
        if not data:
            data = [["(Empty CSV File)"]]

        doc = SimpleDocTemplate(str(output_pdf_path), pagesize=landscape(letter), rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#6366F1")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor("#F8FAFC")),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
        ]))
        doc.build([table])
        pages = count_pdf_pages(output_pdf_path)
        return True, pages, ""
    except Exception as e:
        err_msg = f"CSV ReportLab fallback conversion failed: {str(e)}"
        logger.error(f"[Conversion Error] {err_msg}")
        return False, 0, err_msg

def find_libreoffice_executable() -> str:
    """Locates LibreOffice / soffice binary across Windows and Linux system paths."""
    win_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"
    ]
    for path in win_paths:
        if os.path.exists(path):
            return path

    for exe in ["soffice", "libreoffice"]:
        if shutil.which(exe):
            return exe

    return ""

def convert_office_via_libreoffice(input_path: Path, output_pdf_path: Path) -> tuple[bool, int, str]:
    """
    Converts Word, Excel, PowerPoint, CSV files to PDF using headless LibreOffice.
    Includes 60-second timeout handling and clean error reporting.
    """
    cmd_binary = find_libreoffice_executable()
    if not cmd_binary:
        if input_path.suffix.lower() == ".csv":
            logger.info(f"[Conversion Pipeline] LibreOffice not found. Using ReportLab CSV fallback for '{input_path.name}'.")
            return convert_csv_via_reportlab(input_path, output_pdf_path)
        err_msg = (
            "LibreOffice server binary is not installed or not found in system PATH. "
            "Please install LibreOffice on the host server to convert Word, Excel, PowerPoint, and CSV files."
        )
        logger.warning(f"[Conversion Warning] {err_msg}")
        return False, 0, err_msg

    temp_out_dir = settings.TEMP_DIR / f"soffice_out_{input_path.stem}"
    temp_out_dir.mkdir(parents=True, exist_ok=True)

    try:
        cmd = [
            cmd_binary,
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(temp_out_dir),
            str(input_path)
        ]
        logger.info(f"[Conversion Pipeline] Running LibreOffice command: {' '.join(cmd)}")
        
        timeout_sec = settings.CONVERSION_TIMEOUT_SECONDS
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec
        )

        if result.returncode != 0:
            err_msg = f"LibreOffice conversion exited with status code {result.returncode}: {result.stderr or result.stdout}"
            logger.error(f"[Conversion Error] {err_msg}")
            return False, 0, err_msg

        # LibreOffice names the output file as <input_stem>.pdf
        expected_output = temp_out_dir / f"{input_path.stem}.pdf"
        if not expected_output.exists():
            # Check for any generated PDF file in temp_out_dir as fallback
            pdf_files = list(temp_out_dir.glob("*.pdf"))
            if pdf_files:
                expected_output = pdf_files[0]
            else:
                err_msg = f"LibreOffice finished, but generated PDF file '{expected_output.name}' was not created."
                logger.error(f"[Conversion Error] {err_msg}")
                return False, 0, err_msg

        # Move converted PDF to permanent converted storage
        shutil.move(str(expected_output), str(output_pdf_path))
        pages = count_pdf_pages(output_pdf_path)
        return True, pages, ""

    except subprocess.TimeoutExpired:
        err_msg = f"LibreOffice conversion process timed out after {settings.CONVERSION_TIMEOUT_SECONDS} seconds."
        logger.error(f"[Conversion Timeout] {err_msg}")
        return False, 0, err_msg
    except Exception as e:
        err_msg = f"LibreOffice conversion exception: {str(e)}"
        logger.error(f"[Conversion Exception] {err_msg}")
        return False, 0, err_msg
    finally:
        # Cleanup temporary conversion output folder
        if temp_out_dir.exists():
            shutil.rmtree(str(temp_out_dir), ignore_errors=True)

def process_conversion_pipeline(input_path: Path, output_pdf_path: Path, ext: str) -> tuple[bool, int, str]:
    """Unified format converter dispatcher."""
    ext = ext.lower()

    # 1. Native PDF Pass-Through
    if ext == ".pdf":
        try:
            logger.info(f"[Conversion Pipeline] PDF pass-through for '{input_path.name}'")
            shutil.copy(str(input_path), str(output_pdf_path))
            pages = count_pdf_pages(output_pdf_path)
            return True, pages, ""
        except Exception as e:
            return False, 0, f"PDF pass-through error: {str(e)}"

    # 2. Image Formats (.png, .jpg, .jpeg, .webp, .tiff, .bmp, .gif)
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp", ".gif"):
        logger.info(f"[Conversion Pipeline] Converting image format '{ext}' to PDF...")
        return convert_image_to_pdf(input_path, output_pdf_path)

    # 3. Office & Data Formats (.docx, .doc, .pptx, .ppt, .xlsx, .xls, .csv)
    if ext in (".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls", ".csv"):
        logger.info(f"[Conversion Pipeline] Converting Office format '{ext}' to PDF via LibreOffice...")
        return convert_office_via_libreoffice(input_path, output_pdf_path)

    return False, 0, f"Unsupported file extension: {ext}"

def execute_conversion_job(document_id: int):
    """
    Background worker task executing the conversion pipeline:
    Upload ➔ Temp Storage ➔ Conversion ➔ PDF Storage ➔ Page Count Extraction ➔ DB Update ➔ Cleanup Temp
    """
    db: Session = SessionLocal()
    temp_original_path = None
    try:
        doc = db.query(Document).filter(Document.id == document_id).first()
        if not doc:
            logger.error(f"[Conversion Worker] Document ID {document_id} not found.")
            return

        # Update status to processing
        doc.conversion_status = "processing"
        db.commit()
        db.refresh(doc)
        logger.info(f"[Conversion Worker] Started processing Document #{doc.id} ('{doc.original_filename}')")

        temp_original_path = settings.TEMP_DIR / Path(doc.original_file_path).name
        if not temp_original_path.exists():
            temp_original_path = Path(doc.original_file_path)

        if not temp_original_path.exists():
            doc.conversion_status = "failed"
            doc.conversion_error = "Source input file missing from disk."
            db.commit()
            return

        # Prepare final PDF storage path
        saved_pdf_name = f"{Path(temp_original_path.name).stem}.pdf"
        output_pdf_path = settings.CONVERTED_DIR / saved_pdf_name

        # Execute conversion pipeline
        success, pages, err_msg = process_conversion_pipeline(
            temp_original_path,
            output_pdf_path,
            doc.original_extension
        )

        if success:
            doc.conversion_status = "completed"
            doc.page_count = pages
            doc.pdf_file_path = str(output_pdf_path)
            doc.conversion_error = None
            logger.info(f"[Conversion Worker] Successfully completed Document #{doc.id} ({pages} pages).")
        else:
            doc.conversion_status = "failed"
            doc.conversion_error = err_msg
            logger.error(f"[Conversion Worker] Document #{doc.id} failed: {err_msg}")

        db.commit()
    except Exception as exc:
        logger.error(f"[Conversion Worker Exception] Unhandled error processing Document #{document_id}: {exc}", exc_info=True)
        try:
            doc = db.query(Document).filter(Document.id == document_id).first()
            if doc:
                doc.conversion_status = "failed"
                doc.conversion_error = f"Internal conversion pipeline exception: {str(exc)}"
                db.commit()
        except Exception:
            pass
    finally:
        # Cleanup temporary files
        if temp_original_path and temp_original_path.exists():
            original_path = Path(doc.original_file_path) if doc else None
            if original_path and temp_original_path != original_path:
                try:
                    temp_original_path.unlink()
                except Exception as clean_err:
                    logger.warning(f"Temporary file cleanup failed for '{temp_original_path}': {clean_err}")
        db.close()

