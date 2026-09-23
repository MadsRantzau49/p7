#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

IMAGE = "ghcr.io/mermaid-js/mermaid-cli/mermaid-cli:11.17.0"

BASE_DIR = Path(__file__).resolve().parent

DIAGRAM_DIR = BASE_DIR / "diagrams"
RENDERED_DIR = BASE_DIR / "rendered"

VALID_FORMATS = {"all", "svg", "pdf", "png"}


def render(source: Path, output_format: str) -> None:
    output = RENDERED_DIR / f"{source.stem}.{output_format}"

    command = [
        "docker",
        "run",
        "--rm",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "--volume",
        f"{BASE_DIR}:/data",
        IMAGE,
        "--input",
        f"diagrams/{source.name}",
        "--output",
        f"rendered/{output.name}",
        "--configFile",
        "mermaid-config.json",
        "--backgroundColor",
        "white",
    ]

    if output_format == "pdf":
        command.append("--pdfFit")

    print(f"Rendering {source.name} -> {output.name}")
    subprocess.run(command, check=True)


def main() -> None:
    output_format = sys.argv[1] if len(sys.argv) > 1 else "all"

    if output_format not in VALID_FORMATS:
        print(
            f"Usage: {sys.argv[0]} [all|svg|pdf|png]",
            file=sys.stderr,
        )
        sys.exit(2)

    RENDERED_DIR.mkdir(exist_ok=True)

    if output_format == "all":
        formats = ["svg", "pdf", "png"]
    else:
        formats = [output_format]

    sources = list(DIAGRAM_DIR.glob("*.mmd"))

    if not sources:
        print("No .mmd files found.")
        return

    for fmt in formats:
        for source in sources:
            render(source, fmt)


if __name__ == "__main__":
    main()
