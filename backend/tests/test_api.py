from fastapi.testclient import TestClient

from app.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/health")
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "healthy"
        assert payload["local_only"] is True


def test_video_upload_rejects_unsupported_extension():
    with TestClient(app) as client:
        response = client.post("/api/videos/upload", files={"file": ("notes.txt", b"not a video", "text/plain")})
        assert response.status_code == 415


def test_video_upload_rejects_path_traversal_filename():
    with TestClient(app) as client:
        response = client.post("/api/videos/upload", files={"file": ("../escape.mp4", b"bad", "video/mp4")})
        assert response.status_code in {400, 422}

