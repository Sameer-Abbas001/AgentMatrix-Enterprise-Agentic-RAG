from io import BytesIO

import pytest
from docx import Document
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from agentmatrix.api import app
from agentmatrix.documents import MAX_FILE_BYTES


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def _upload(client, filename, data):
    return client.post("/v1/policies/extract", params={"filename": filename}, content=data)


def _pdf() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"),
        NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
    })
    contents = DecodedStreamObject()
    contents.set_data(b"BT /F1 12 Tf 36 700 Td (Meal reimbursements are capped at $25.) Tj ET")
    page.replace_contents(contents)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_extract_pdf_text(client):
    response = _upload(client, "Expenses.pdf", _pdf())
    assert response.status_code == 200
    assert response.json() == {
        "title": "Expenses.pdf",
        "text": "Meal reimbursements are capped at $25.",
    }


def test_extract_word_paragraphs_and_tables(client):
    document = Document()
    document.add_paragraph("Employee expenses")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Meal reimbursement"
    table.cell(0, 1).text = "$25"
    buffer = BytesIO()
    document.save(buffer)

    response = _upload(client, "Expenses.docx", buffer.getvalue())
    assert response.status_code == 200
    assert response.json()["text"] == "Employee expenses\nMeal reimbursement | $25"


@pytest.mark.parametrize(
    ("filename", "data", "status"),
    [
        ("leave.txt", b"Annual leave is 20 days.", 200),
        ("leave.md", b"# Leave\nAnnual leave is 20 days.", 200),
        ("empty.txt", b"   ", 422),
        ("broken.pdf", b"bad data", 422),
        ("broken.docx", b"bad data", 422),
        ("unknown.exe", b"data", 422),
        ("long.txt", b"a" * 40_001, 422),
        ("large.txt", b"a" * (MAX_FILE_BYTES + 1), 413),
    ],
    ids=["txt", "markdown", "empty", "invalid-pdf", "invalid-docx", "unknown", "long", "large"],
)
def test_upload_formats_and_limits(client, filename, data, status):
    response = _upload(client, filename, data)
    assert response.status_code == status
