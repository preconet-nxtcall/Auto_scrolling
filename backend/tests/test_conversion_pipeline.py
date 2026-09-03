import io
import zipfile
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    user = User(
        id=1, email="test@autoscroll.io", full_name="Test User", is_active=True
    )
    db.add(user)
    db.commit()
    db.close()
    yield


def make_sample_image() -> bytes:
    img = Image.new("RGB", (200, 200), color=(99, 102, 241))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def make_sample_pdf() -> bytes:
    # Basic valid 1-page PDF binary
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 300 300]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000052 00000 n\n00000000102 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n168\n%%EOF"
    )


def make_sample_csv() -> bytes:
    return b"Title,Category,Value\nItem A,Tech,100\nItem B,Design,200\n"


def make_sample_openxml_zip() -> bytes:
    # Basic valid zip structure mimicking openxml office file
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("[Content_Types].xml", "<Types></Types>")
    return buf.getvalue()


def test_upload_and_convert_pdf():
    pdf_bytes = make_sample_pdf()
    files = [("files", ("sample.pdf", pdf_bytes, "application/pdf"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] == "completed"
    assert status_res.json()["page_count"] == 1


def test_upload_and_convert_image():
    img_bytes = make_sample_image()
    files = [("files", ("image.png", img_bytes, "image/png"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] == "completed"
    assert status_res.json()["page_count"] >= 1


def test_upload_and_convert_csv():
    csv_bytes = make_sample_csv()
    files = [("files", ("data.csv", csv_bytes, "text/csv"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] == "completed"
    assert status_res.json()["page_count"] >= 1


def test_upload_docx():
    docx_bytes = make_sample_openxml_zip()
    files = [(
        "files",
        ("report.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    )]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]
    assert res.json()[0]["original_extension"] == ".docx"

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] in ("completed", "failed")


def test_upload_pptx():
    pptx_bytes = make_sample_openxml_zip()
    files = [(
        "files",
        ("presentation.pptx", pptx_bytes, "application/vnd.openxmlformats-officedocument.presentationml.presentation")
    )]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]
    assert res.json()[0]["original_extension"] == ".pptx"

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] in ("completed", "failed")


def test_upload_xlsx():
    xlsx_bytes = make_sample_openxml_zip()
    files = [(
        "files",
        ("sheet.xlsx", xlsx_bytes, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    )]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]
    assert res.json()[0]["original_extension"] == ".xlsx"

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] in ("completed", "failed")


def test_invalid_corrupted_file():
    files = [("files", ("broken.pdf", b"INVALID_DATA", "application/pdf"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 400
    assert "Corrupted PDF" in res.json()["detail"]


def test_retry_conversion_endpoint():
    pdf_bytes = make_sample_pdf()
    files = [("files", ("retry_doc.pdf", pdf_bytes, "application/pdf"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    doc_id = res.json()[0]["id"]

    retry_res = client.post(
        f"/api/documents/{doc_id}/retry", headers={"X-User-Id": "1"}
    )
    assert retry_res.status_code == 200

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] in (
        "completed", "processing", "uploaded"
    )


def test_upload_and_convert_html():
    html_bytes = b"<!DOCTYPE html><html><head><title>Test</title></head><body><h1>Hello HTML</h1><p>Sample presentation content.</p></body></html>"
    files = [("files", ("page.html", html_bytes, "text/html"))]
    res = client.post(
        "/api/documents/upload", files=files, headers={"X-User-Id": "1"}
    )
    assert res.status_code == 201
    doc_id = res.json()[0]["id"]
    assert res.json()[0]["original_extension"] == ".html"

    status_res = client.get(
        f"/api/documents/{doc_id}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] == "completed"
    assert status_res.json()["page_count"] >= 1



