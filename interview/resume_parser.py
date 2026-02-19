import os
from PyPDF2 import PdfReader
from docx import Document


def parse_resume(file_path):
    """
    Extract text content from a resume file (PDF or DOCX).
    Returns the extracted text as a string.
    """
    file_path = str(file_path)
    ext = os.path.splitext(file_path)[1].lower()

    if ext == '.pdf':
        return _parse_pdf(file_path)
    elif ext == '.docx':
        return _parse_docx(file_path)
    else:
        raise ValueError(f"Unsupported file format: {ext}")


def _parse_pdf(file_path):
    """Extract text from a PDF file."""
    text_parts = []
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    except Exception as e:
        raise ValueError(f"Error reading PDF: {str(e)}")

    text = '\n'.join(text_parts).strip()
    if not text:
        raise ValueError("Could not extract any text from the PDF. The file may be scanned/image-based.")
    return text


def _parse_docx(file_path):
    """Extract text from a DOCX file."""
    text_parts = []
    try:
        doc = Document(file_path)
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text.strip())
    except Exception as e:
        raise ValueError(f"Error reading DOCX: {str(e)}")

    text = '\n'.join(text_parts).strip()
    if not text:
        raise ValueError("Could not extract any text from the DOCX file.")
    return text
