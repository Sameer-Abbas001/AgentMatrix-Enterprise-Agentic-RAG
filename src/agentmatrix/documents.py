from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from docx import Document as WordDocument
from docx.opc.exceptions import PackageNotFoundError
from docx.text.paragraph import Paragraph
from lxml.etree import XMLSyntaxError
from pydantic import BaseModel, Field
from pypdf import PdfReader
from pypdf.errors import PyPdfError

from agentmatrix.retrieval import Document

MAX_POLICIES = 8
MAX_FILE_BYTES = 2 * 1024 * 1024
MAX_POLICY_CHARS = 40_000
MAX_PDF_PAGES = 25
MAX_PDF_STREAM_BYTES = 1024 * 1024
MAX_DOCX_UNPACKED_BYTES = 12 * 1024 * 1024
PASSAGE_CHARS = 1_200
PASSAGE_OVERLAP = 150
FILE_TYPES = {".pdf", ".docx", ".txt", ".md"}


class PolicyText(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    text: str = Field(min_length=1, max_length=MAX_POLICY_CHARS)


class PolicyFileError(ValueError):
    pass


def _pdf_blocks(data: bytes) -> Iterator[str]:
    pdf = PdfReader(BytesIO(data))
    if pdf.is_encrypted:
        raise PolicyFileError("Choose a PDF without password protection.")
    if len(pdf.pages) > MAX_PDF_PAGES:
        raise PolicyFileError(f"Split the PDF into files with up to {MAX_PDF_PAGES} pages.")
    for page in pdf.pages:
        contents = page.get_contents()
        if contents and len(contents.get_data()) > MAX_PDF_STREAM_BYTES:
            raise PolicyFileError("This PDF is too complex. Export it as TXT or DOCX.")
        yield page.extract_text()


def _docx_blocks(data: bytes) -> Iterator[str]:
    with ZipFile(BytesIO(data)) as archive:
        expanded_size = sum(entry.file_size for entry in archive.infolist())
        if expanded_size > MAX_DOCX_UNPACKED_BYTES:
            raise PolicyFileError("This Word file is too complex. Export it as TXT.")
    document = WordDocument(BytesIO(data))
    for block in document.iter_inner_content():
        if isinstance(block, Paragraph):
            yield block.text
        else:
            for row in block.rows:
                yield " | ".join(cell.text for cell in row.cells)


def extract_policy(filename: str, data: bytes) -> PolicyText:
    name = PurePosixPath(filename.replace("\\", "/")).name.strip()
    suffix = PurePosixPath(name).suffix.lower()
    if suffix not in FILE_TYPES:
        raise PolicyFileError("Choose a PDF, DOCX, TXT, or Markdown file.")

    parts: list[str] = []
    total = 0
    try:
        if suffix == ".pdf":
            blocks = _pdf_blocks(data)
        elif suffix == ".docx":
            blocks = _docx_blocks(data)
        else:
            blocks = (data.decode("utf-8-sig"),)
        for block in blocks:
            clean = block.strip()
            if not clean:
                continue
            total += len(clean) + bool(parts)
            if total > MAX_POLICY_CHARS:
                raise PolicyFileError(
                    f"Split the file into parts of up to {MAX_POLICY_CHARS:,} characters."
                )
            parts.append(clean)
    except PolicyFileError:
        raise
    except (
        BadZipFile,
        PackageNotFoundError,
        XMLSyntaxError,
        PyPdfError,
        KeyError,
        TypeError,
        RuntimeError,
        ValueError,
    ) as exc:
        raise PolicyFileError("This file could not be read. Try a different export.") from exc
    text = "\n".join(parts)
    if not any(character.isalnum() for character in text):
        raise PolicyFileError("No readable text found. Choose a file with selectable text.")
    return PolicyText(title=name, text=text)


def policy_passages(policies: list[PolicyText]) -> list[Document]:
    passages: list[Document] = []
    for file_number, policy in enumerate(policies, 1):
        text = " ".join(policy.text.split())
        start = 0
        part = 1
        while start < len(text):
            end = min(start + PASSAGE_CHARS, len(text))
            if end < len(text):
                boundary = text.rfind(" ", end - PASSAGE_OVERLAP, end)
                if boundary >= 0:
                    end = boundary
            passages.append(
                Document(f"policy-{file_number}-{part}", policy.title, text[start:end])
            )
            if end == len(text):
                break
            overlap_start = end - PASSAGE_OVERLAP
            boundary = text.find(" ", overlap_start, end)
            start = overlap_start if boundary < 0 else boundary + 1
            part += 1
    return passages
