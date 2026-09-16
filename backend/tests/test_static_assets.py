from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

from backend.app.api.static_assets import build_assets


def test_assets_compress_and_cache_without_touching_api_streams(tmp_path):
    content = "console.log('static asset');\n" * 500
    (tmp_path / "index-abcdefgh.js").write_bytes(content.encode())
    (tmp_path / "plain.js").write_bytes(content.encode())
    app = FastAPI()
    app.mount("/assets", build_assets(tmp_path))

    @app.get("/api/events")
    def events():
        return StreamingResponse(iter(["data: " + "x" * 2000 + "\n\n"]), media_type="text/event-stream")

    client = TestClient(app)
    response = client.get("/assets/index-abcdefgh.js", headers={"Accept-Encoding": "gzip"})
    assert response.text == content
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["content-encoding"] == "gzip"
    assert "Accept-Encoding" in response.headers["vary"]
    assert "immutable" in response.headers["cache-control"]
    assert int(response.headers["content-length"]) < len(content) / 2
    plain = client.get("/assets/index-abcdefgh.js", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in plain.headers
    assert plain.text == content
    cached = client.get("/assets/index-abcdefgh.js", headers={"If-None-Match": plain.headers["etag"]})
    assert cached.status_code == 304
    assert "immutable" in cached.headers["cache-control"]
    assert client.get("/assets/plain.js").headers["cache-control"] == "no-cache"
    assert client.get("/assets/missing-abcdefgh.js").status_code == 404
    events = client.get("/api/events", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in events.headers
    assert "cache-control" not in events.headers
