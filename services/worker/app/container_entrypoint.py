"""Run Celery alongside a small HTTP health endpoint for Cloudflare Containers."""
from __future__ import annotations

import signal
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    worker: subprocess.Popen[bytes]

    def do_GET(self) -> None:
        if self.path != "/health":
            self.send_error(404)
            return

        status = 200 if self.worker.poll() is None else 503
        self.send_response(status)
        self.end_headers()
        self.wfile.write(b"ok" if status == 200 else b"worker stopped")

    def log_message(self, _format: str, *_args: object) -> None:
        return


def main() -> None:
    worker = subprocess.Popen(
        [
            "celery",
            "-A",
            "app.celery_app",
            "worker",
            "-Q",
            "transcription,embedding,features",
            "-c",
            "2",
            "--loglevel=info",
        ]
    )
    HealthHandler.worker = worker
    server = ThreadingHTTPServer(("0.0.0.0", 8002), HealthHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    stopping = threading.Event()

    def stop_worker(_signum: int, _frame: object) -> None:
        stopping.set()
        if worker.poll() is None:
            worker.terminate()

    signal.signal(signal.SIGTERM, stop_worker)
    signal.signal(signal.SIGINT, stop_worker)

    try:
        while worker.poll() is None and not stopping.wait(1):
            pass
    finally:
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=30)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait()
        server.shutdown()
        server.server_close()

    if worker.returncode:
        raise SystemExit(worker.returncode)


if __name__ == "__main__":
    main()
