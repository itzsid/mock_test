"""CLI entry points for pyexam."""

import shutil
import subprocess
import sys
import time
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
DATA_FILES = ["server.py", "index.html"]


def _find_open_port(start=3000, attempts=100):
    import socket
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start


def _start_server(work_dir):
    port = _find_open_port()
    proc = subprocess.Popen(
        [sys.executable, "server.py", str(port)],
        cwd=str(work_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    time.sleep(1.5)

    if proc.poll() is not None:
        out = proc.stdout.read().decode() if proc.stdout else ""
        print(f"Server failed to start:\n{out}", file=sys.stderr)
        sys.exit(1)

    url = f"http://localhost:{port}"
    print(f"  URL:    {url}")
    print(f"  Folder: {work_dir}")
    print()

    if sys.platform == "darwin":
        subprocess.run(["open", url], check=False)
    elif sys.platform == "linux":
        subprocess.run(["xdg-open", url], check=False)

    print("Press Ctrl+C to stop.")
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        proc.wait(timeout=5)
        print("\nServer stopped.")


def main():
    """Start PyExam mock test server."""
    work_dir = Path.cwd()

    # Copy data files to working directory if not present
    for f in DATA_FILES:
        src = DATA_DIR / f
        dst = work_dir / f
        if src.exists() and not dst.exists():
            shutil.copy2(src, dst)

    # Ensure tests directory exists
    (work_dir / "tests").mkdir(exist_ok=True)

    print("Starting PyExam...\n")
    _start_server(work_dir)
