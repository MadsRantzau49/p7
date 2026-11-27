"""Serve the trajectory builder and save its generated test fixtures."""

import csv
import io
import json
import os
import re
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from trajectory_builder.schema import DATA_DIRECTORY as DEFAULT_DATA_DIRECTORY
from trajectory_builder.schema import HEADER

UI_DIRECTORY = Path(__file__).parent / "ui"
DATA_DIRECTORY = Path(os.getenv("TRAJECTORY_DATA_DIR", str(DEFAULT_DATA_DIRECTORY)))


def save_fixture(name: str, csv_data: str) -> Path:
    """Save a CSV fixture without overwriting an existing route."""
    if re.fullmatch(r"[a-z0-9_-]+", name) is None:
        raise ValueError("Name must use lowercase letters, numbers, underscores, or hyphens")

    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    if name.startswith("bench_"):
        name = f"manual_{name}"  # bench_ is reserved for explicitly sized bulk tests.
    number = 1
    while True:
        candidate = name if number == 1 else f"{name}_{number}"
        output_path = DATA_DIRECTORY / f"{candidate}.csv"
        try:
            with output_path.open("x", encoding="utf-8", newline="") as stream:
                stream.write(csv_data)
            return output_path
        except FileExistsError:
            number += 1


def fixture_name_from_csv(csv_data: str) -> str:
    """Use the first trajectory grouping key as the fixture filename."""
    reader = csv.reader(io.StringIO(csv_data, newline=""))
    header = next(reader, None)
    first_row = next(reader, None)

    if header != list(HEADER) or not first_row:
        raise ValueError("Expected the trajectory builder CSV columns and at least one GPS point")

    return first_row[0]


class TrajectoryBuilderHandler(SimpleHTTPRequestHandler):
    """Serve the builder UI and accept generated fixtures at `/fixtures`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=UI_DIRECTORY, **kwargs)

    def end_headers(self):
        """Prevent stale builder assets after the local server is rebuilt."""
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        """Expose the shared CSV columns alongside the map UI."""
        if urlsplit(self.path).path == "/fixture-columns":
            self._send_json(HTTPStatus.OK, {"columns": HEADER})
        else:
            super().do_GET()

    def do_POST(self):
        """Save a fixture sent by the builder UI."""
        request_url = urlsplit(self.path)
        if request_url.path != "/fixtures":
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        try:
            csv_data = self._read_text_body()
            output_path = save_fixture(fixture_name_from_csv(csv_data), csv_data)
        except (UnicodeDecodeError, ValueError) as error:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(error)})
            return

        self._send_json(
            HTTPStatus.CREATED,
            {"path": f"backend/tests/data/trajectories/{output_path.name}"},
        )

    def _read_text_body(self) -> str:
        content_length = int(self.headers.get("Content-Length", "0"))
        if not 0 < content_length <= 16 * 1024**2:
            raise ValueError("Expected a map fixture between 1 byte and 16 MiB")
        return self.rfile.read(content_length).decode("utf-8")

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
