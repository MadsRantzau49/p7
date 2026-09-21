"""Serve the trajectory builder and save its generated test fixtures."""

import json
import os
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

UI_DIRECTORY = Path(__file__).parent / "ui"
DEFAULT_DATA_DIRECTORY = Path(__file__).parent.parent / "data" / "trajectories"
DATA_DIRECTORY = Path(os.getenv("TRAJECTORY_DATA_DIR", str(DEFAULT_DATA_DIRECTORY)))


def save_fixture(fixture: dict) -> Path:
    """Validate and save a fixture without overwriting an existing route."""
    name = fixture.get("name")
    if not isinstance(name, str):
        raise ValueError("Name must be a string")

    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    unique_name = available_name(name)
    output_path = DATA_DIRECTORY / f"{unique_name}.json"
    saved_fixture = {**fixture, "name": unique_name}
    output_path.write_text(json.dumps(saved_fixture, indent=2) + "\n", encoding="utf-8")
    output_path.chmod(0o666)
    return output_path


def available_name(name: str) -> str:
    """Add a number when a fixture with the requested name already exists."""
    candidate = name
    number = 2

    while (DATA_DIRECTORY / f"{candidate}.json").exists():
        candidate = f"{name}_{number}"
        number += 1

    return candidate


class TrajectoryBuilderHandler(SimpleHTTPRequestHandler):
    """Serve the builder UI and accept generated fixtures at `/fixtures`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIRECTORY, **kwargs)

    def do_POST(self):
        """Save a fixture sent by the builder UI."""
        if self.path != "/fixtures":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            fixture = self._read_json_body()
            output_path = save_fixture(fixture)
        except (TypeError, ValueError, json.JSONDecodeError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        self._send_json(
            HTTPStatus.CREATED,
            {"path": f"backend/tests/data/trajectories/{output_path.name}"},
        )

    def _read_json_body(self) -> dict:
        content_length = int(self.headers.get("Content-Length", "0"))
        return json.loads(self.rfile.read(content_length))

    def _send_json(self, status: HTTPStatus, data: dict):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server() -> None:
    """Run the local trajectory builder server."""
    port = int(os.getenv("PORT", "80"))
    server = ThreadingHTTPServer(("0.0.0.0", port), TrajectoryBuilderHandler)
    server.serve_forever()


if __name__ == "__main__":
    run_server()
