import io
import re
from pathlib import Path
import pandas as pd

try:
    from pypdf import PdfReader
except ImportError:
    from PyPDF2 import PdfReader

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


def extract_text_from_pdf(file_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(file_bytes))
    pages = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text.strip())
    return "\n\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    if DocxDocument is None:
        raise ImportError("python-docx not installed")
    doc = DocxDocument(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def extract_text_from_txt(file_bytes: bytes) -> str:
    for encoding in ["utf-8", "latin-1", "cp1252"]:
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    return file_bytes.decode("utf-8", errors="replace")


def read_dataframe(file_bytes: bytes, filename: str) -> pd.DataFrame:
    ext = Path(filename).suffix.lower()
    if ext in [".xlsx", ".xls"]:
        return pd.read_excel(io.BytesIO(file_bytes))
    elif ext == ".csv":
        for sep in [",", ";", "\t", "|"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), sep=sep)
                if len(df.columns) > 1:
                    return df
            except Exception:
                continue
        return pd.read_csv(io.BytesIO(file_bytes))
    raise ValueError(f"Unsupported file type: {ext}")


def extract_text_from_file(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_text_from_pdf(file_bytes)
    elif ext in [".docx", ".doc"]:
        return extract_text_from_docx(file_bytes)
    elif ext in [".txt", ".md"]:
        return extract_text_from_txt(file_bytes)
    elif ext in [".xlsx", ".xls", ".csv"]:
        df = read_dataframe(file_bytes, filename)
        return df.to_string(index=False)
    raise ValueError(f"Unsupported file type: {ext}")


def chunk_text_recursive(
    text: str,
    chunk_size: int = 1000,
    chunk_overlap: int = 150,
) -> list[str]:
    separators = ["\n\n", "\n", ". ", " ", ""]
    chunks = _split_recursive(text, separators, chunk_size, chunk_overlap)
    return [c.strip() for c in chunks if c.strip() and len(c.strip()) > 50]


def _split_recursive(text: str, separators: list[str], chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    if not separators:
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]

    sep = separators[0]
    remaining = separators[1:]

    if sep == "":
        parts = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size - overlap)]
        return parts

    splits = text.split(sep)
    chunks = []
    current = ""

    for split in splits:
        candidate = current + (sep if current else "") + split
        if len(candidate) <= chunk_size:
            current = candidate
        else:
            if current:
                chunks.append(current)
            if len(split) > chunk_size:
                sub_chunks = _split_recursive(split, remaining, chunk_size, overlap)
                chunks.extend(sub_chunks[:-1])
                current = sub_chunks[-1] if sub_chunks else ""
            else:
                current = split

    if current:
        chunks.append(current)

    if overlap > 0:
        overlapped = []
        for i, chunk in enumerate(chunks):
            if i > 0 and len(overlapped) > 0:
                prev_end = overlapped[-1][-overlap:]
                chunk = prev_end + " " + chunk
            overlapped.append(chunk)
        return overlapped

    return chunks


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x20-\x7E\n]', ' ', text)
    text = re.sub(r' {3,}', '  ', text)
    return text.strip()


def get_file_type_label(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    type_map = {
        ".pdf": "PDF Document",
        ".docx": "Word Document",
        ".doc": "Word Document",
        ".xlsx": "Excel Spreadsheet",
        ".xls": "Excel Spreadsheet",
        ".csv": "CSV Data",
        ".txt": "Text File",
        ".md": "Markdown File",
    }
    return type_map.get(ext, "Document")
