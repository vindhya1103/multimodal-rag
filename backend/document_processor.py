"""
document_processor.py — Multimodal document extraction.

Handles:
  - PDFs  → text via PyMuPDF + tables via pdfplumber
  - Images → OCR via pytesseract (graceful fallback if not installed)
"""
import os
import fitz  # PyMuPDF
import pdfplumber
from PIL import Image
from langchain_core.documents import Document


def _pdf_text(file_path: str) -> list[Document]:
    """Extract plain text from each PDF page."""
    docs = []
    filename = os.path.basename(file_path)
    pdf = fitz.open(file_path)
    for page_num, page in enumerate(pdf, start=1):
        text = page.get_text("text").strip()
        if text:
            docs.append(Document(
                page_content=text,
                metadata={"source": filename, "page": page_num, "type": "text"},
            ))
    pdf.close()
    return docs


def _pdf_tables(file_path: str) -> list[Document]:
    """Extract tables from PDF and convert to readable text."""
    docs = []
    filename = os.path.basename(file_path)
    try:
        with pdfplumber.open(file_path) as pdf:
            for page_num, page in enumerate(pdf.pages, start=1):
                for table in page.extract_tables() or []:
                    if not table:
                        continue
                    rows = [
                        " | ".join(str(cell or "").strip() for cell in row)
                        for row in table
                    ]
                    table_text = "\n".join(rows).strip()
                    if table_text:
                        docs.append(Document(
                            page_content=f"[TABLE from page {page_num}]\n{table_text}",
                            metadata={"source": filename, "page": page_num, "type": "table"},
                        ))
    except Exception:
        pass  # pdfplumber failure is non-fatal
    return docs


def _image_ocr(file_path: str) -> list[Document]:
    """Extract text from an image using pytesseract OCR."""
    filename = os.path.basename(file_path)
    fallback = Document(
        page_content=f"[IMAGE: {filename}] No text could be extracted.",
        metadata={"source": filename, "page": 1, "type": "image"},
    )
    try:
        import pytesseract
        # Auto-detect Tesseract on Windows
        for path in [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]:
            if os.path.exists(path):
                pytesseract.pytesseract.tesseract_cmd = path
                break

        img = Image.open(file_path).convert("RGB")
        text = pytesseract.image_to_string(img).strip()
        if text:
            return [Document(
                page_content=f"[IMAGE TEXT from {filename}]\n{text}",
                metadata={"source": filename, "page": 1, "type": "image"},
            )]
        return [fallback]

    except ImportError:
        return [Document(
            page_content=f"[IMAGE: {filename}] Install Tesseract-OCR for text extraction from images.",
            metadata={"source": filename, "page": 1, "type": "image"},
        )]
    except Exception as e:
        return [Document(
            page_content=f"[IMAGE: {filename}] OCR error: {str(e)}",
            metadata={"source": filename, "page": 1, "type": "image"},
        )]


def process_file(file_path: str) -> list[Document]:
    """
    Auto-detect file type and extract all content.
    Returns a flat list of LangChain Document objects.
    """
    ext = file_path.rsplit(".", 1)[-1].lower()
    if ext == "pdf":
        docs = _pdf_text(file_path) + _pdf_tables(file_path)
        if not docs:
            raise ValueError("Could not extract any text from this PDF.")
        return docs
    elif ext in ("png", "jpg", "jpeg", "bmp", "tiff", "webp"):
        return _image_ocr(file_path)
    else:
        raise ValueError(f"Unsupported file type: .{ext}")