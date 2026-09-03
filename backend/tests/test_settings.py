from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_get_and_update_user_global_settings():
    """Test fetching and updating global auto-scroll settings."""
    headers = {"X-User-Id": "1"}

    # 1. Fetch default global settings
    res = client.get("/api/settings", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert data["global_scroll_speed"] == 50
    assert data["global_repeat_count"] == 3
    assert data["global_interaction_pause"] == 3000

    # 2. Update global settings
    update_payload = {
        "global_scroll_speed": 120,
        "global_repeat_count": 5,
        "global_interaction_pause": 4000,
        "global_start_delay": 3000
    }
    res = client.put("/api/settings", json=update_payload, headers=headers)
    assert res.status_code == 200
    updated_data = res.json()
    assert updated_data["global_scroll_speed"] == 120
    assert updated_data["global_repeat_count"] == 5
    assert updated_data["global_interaction_pause"] == 4000
    assert updated_data["global_start_delay"] == 3000


def test_global_settings_range_validation():
    """Test range validation for global settings (rejecting bad values)."""
    headers = {"X-User-Id": "1"}

    # Negative scroll speed
    res = client.put(
        "/api/settings", json={"global_scroll_speed": -10}, headers=headers
    )
    assert res.status_code == 422

    # Zero repeat count
    res = client.put(
        "/api/settings", json={"global_repeat_count": 0}, headers=headers
    )
    assert res.status_code == 422

    # Excessively large speed (>500)
    res = client.put(
        "/api/settings", json={"global_scroll_speed": 1000}, headers=headers
    )
    assert res.status_code == 422


def test_document_settings_override_and_inheritance():
    """Test per-document override settings and global inheritance."""
    headers = {"X-User-Id": "1"}

    # Reset global settings first
    client.put("/api/settings", json={
        "global_scroll_speed": 50,
        "global_repeat_count": 3
    }, headers=headers)

    # Upload a dummy document using valid PDF binary structure
    pdf_bytes = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 300 300]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n"
        b"0000000052 00000 n\n00000000102 00000 n\n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n168\n%%EOF"
    )
    files = {"files": ("sample_test.pdf", pdf_bytes, "application/pdf")}
    res = client.post("/api/documents/upload", files=files, headers=headers)
    assert res.status_code == 201
    doc = res.json()[0]
    doc_id = doc["id"]

    # 1. New document has NULL overrides -> inherits global settings
    assert doc["scroll_speed"] is None
    assert doc["repeat_count"] is None
    assert doc["effective_settings"]["scroll_speed"] == 50
    assert doc["effective_settings"]["repeat_count"] == 3

    # 2. Update Document A with custom override: repeat_count = 5
    res = client.patch(
        f"/api/documents/{doc_id}", json={"repeat_count": 5}, headers=headers
    )
    assert res.status_code == 200
    updated_doc = res.json()
    assert updated_doc["repeat_count"] == 5
    assert updated_doc["scroll_speed"] is None
    assert updated_doc["effective_settings"]["repeat_count"] == 5
    assert updated_doc["effective_settings"]["scroll_speed"] == 50

    # 3. Reset Document override back to NULL (Inherit Global)
    res = client.patch(
        f"/api/documents/{doc_id}", json={"repeat_count": None}, headers=headers
    )
    assert res.status_code == 200
    reset_doc = res.json()
    assert reset_doc["repeat_count"] is None
    assert reset_doc["effective_settings"]["repeat_count"] == 3

