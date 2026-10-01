from fastapi.testclient import TestClient

from main import app


client = TestClient(app)


def test_app_metadata():
    """Check FastAPI app metadata."""
    assert app.title == "Trajectory API"
    assert app.version == "0.0.1"


def test_openapi_available():
    """Check that the API can generate its OpenAPI schema."""
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Trajectory API"
    assert response.json()["info"]["version"] == "0.0.1"


def test_cors_allows_frontend_origin():
    """Check that the frontend origin is allowed by CORS."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_cors_rejects_unknown_origin():
    """Check that unknown origins are not allowed."""
    response = client.options(
        "/",
        headers={
            "Origin": "http://example.com",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers