import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app
from app.database import Base, engine, SessionLocal
from app.models import User

client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_test_database():
    """Reset database tables before each test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    # Create two test users for user isolation testing
    db = SessionLocal()
    user1 = User(
        id=1, email="user1@example.com", full_name="User One", is_active=True
    )
    user2 = User(
        id=2, email="user2@example.com", full_name="User Two", is_active=True
    )
    db.add_all([user1, user2])
    db.commit()
    db.close()
    yield


def create_sample_png_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color=(79, 70, 229))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_document_upload_success():
    png_bytes = create_sample_png_bytes()
    files = [
        ("files", ("test_image.png", png_bytes, "image/png"))
    ]
    response = client.post(
        "/api/documents/upload",
        files=files,
        data={"scroll_speed": 60, "repeat_count": 3},
        headers={"X-User-Id": "1"}
    )
    assert response.status_code == 201
    data = response.json()
    assert len(data) == 1
    doc = data[0]
    assert doc["user_id"] == 1
    assert doc["original_filename"] == "test_image.png"
    assert doc["original_extension"] == ".png"
    assert doc["conversion_status"] in (
        "uploaded", "processing", "completed"
    )

    # Check status endpoint after background job completes
    status_res = client.get(
        f"/api/documents/{doc['id']}/status", headers={"X-User-Id": "1"}
    )
    assert status_res.status_code == 200
    assert status_res.json()["conversion_status"] == "completed"
    assert status_res.json()["page_count"] == 1
    assert doc["scroll_speed"] == 60
    assert doc["repeat_count"] == 3


def test_upload_disallowed_extension():
    files = [
        ("files", ("malicious.exe", b"binary content", "application/x-msdownload"))
    ]
    response = client.post(
        "/api/documents/upload",
        files=files,
        headers={"X-User-Id": "1"}
    )
    assert response.status_code == 400
    assert "Invalid file extension" in response.json()["detail"]


def test_upload_corrupted_file():
    files = [
        ("files", ("corrupted.pdf", b"NOT_A_VALID_PDF_HEADER", "application/pdf"))
    ]
    response = client.post(
        "/api/documents/upload",
        files=files,
        headers={"X-User-Id": "1"}
    )
    assert response.status_code == 400
    assert "Corrupted PDF file header" in response.json()["detail"]


def test_user_isolation():
    # User 1 uploads document
    png_bytes = create_sample_png_bytes()
    files = [("files", ("user1_doc.png", png_bytes, "image/png"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        headers={"X-User-Id": "1"}
    )
    assert upload_res.status_code == 201
    doc_id = upload_res.json()[0]["id"]

    # User 1 lists documents (should see 1)
    res_u1 = client.get("/api/documents", headers={"X-User-Id": "1"})
    assert len(res_u1.json()) == 1

    # User 2 lists documents (should see 0)
    res_u2 = client.get("/api/documents", headers={"X-User-Id": "2"})
    assert len(res_u2.json()) == 0

    # User 2 tries to get User 1's document (should be 404)
    get_res = client.get(
        f"/api/documents/{doc_id}", headers={"X-User-Id": "2"}
    )
    assert get_res.status_code == 404

    # User 2 tries to stream User 1's PDF (should be 404)
    stream_res = client.get(
        f"/api/documents/{doc_id}/pdf", headers={"X-User-Id": "2"}
    )
    assert stream_res.status_code == 404

    # User 2 tries to delete User 1's document (should be 404)
    del_res = client.delete(
        f"/api/documents/{doc_id}", headers={"X-User-Id": "2"}
    )
    assert del_res.status_code == 404

    # User 1 deletes their own document (should be 204)
    own_del = client.delete(
        f"/api/documents/{doc_id}", headers={"X-User-Id": "1"}
    )
    assert own_del.status_code == 204


def test_get_document_pdf_stream():
    png_bytes = create_sample_png_bytes()
    files = [("files", ("stream_test.png", png_bytes, "image/png"))]
    upload_res = client.post(
        "/api/documents/upload",
        files=files,
        headers={"X-User-Id": "1"}
    )
    doc_id = upload_res.json()[0]["id"]

    pdf_res = client.get(
        f"/api/documents/{doc_id}/pdf", headers={"X-User-Id": "1"}
    )
    assert pdf_res.status_code == 200
    assert pdf_res.headers["content-type"] == "application/pdf"
    assert pdf_res.content.startswith(b"%PDF-")

