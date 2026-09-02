#!/usr/bin/env python3
"""Stdlib server for the Evidence Integrity Board. Runs the orchestrator on start and on
GET /api/run; serves board.html + combined_board.json. No framework."""
from __future__ import annotations
import os, json, subprocess, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).parent
PORT = int(os.environ.get("PORT", "8090"))


def run_all():
    subprocess.run(["python3", str(HERE / "orchestrate.py")], check=False)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/run"):
            run_all()
            return self._send(200, (HERE / "combined_board.json").read_text(), "application/json")
        if self.path.startswith("/api/board"):
            p = HERE / "combined_board.json"
            if not p.exists():
                run_all()
            return self._send(200, p.read_text(), "application/json")
        if self.path in ("/", "/index.html", "/board.html"):
            return self._send(200, (HERE / "board.html").read_text(), "text/html; charset=utf-8")
        if self.path == "/health":
            return self._send(200, json.dumps({"ok": True, "deploy": os.environ.get("DROPLET_HOST", "137.184.1.91")}), "application/json")
        return self._send(404, json.dumps({"error": "not found"}), "application/json")


if __name__ == "__main__":
    run_all()
    print(f"[evidence-integrity] board on :{PORT}  · deploy {os.environ.get('DROPLET_HOST','137.184.1.91')}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
