#!/usr/bin/env python3
"""Tiny stdlib server for the citation-integrity monitor. Runs the engine on start
and on GET /api/run; serves the dashboard + dashboard_data.json. No framework."""
from __future__ import annotations
import os, json, subprocess, pathlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = pathlib.Path(__file__).parent
PORT = int(os.environ.get("PORT", "8091"))


def run_engine():
    subprocess.run(["python3", str(HERE / "link_verify.py")], check=False)


class H(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code, body, ctype):
        b = body if isinstance(body, bytes) else body.encode()
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(b))); self.end_headers(); self.wfile.write(b)

    def do_GET(self):
        if self.path.startswith("/api/run"):
            run_engine()
            return self._send(200, (HERE / "dashboard_data.json").read_text(), "application/json")
        if self.path.startswith("/api/data"):
            p = HERE / "dashboard_data.json"
            if not p.exists():
                run_engine()
            return self._send(200, p.read_text(), "application/json")
        if self.path in ("/", "/index.html", "/dashboard.html"):
            return self._send(200, (HERE / "dashboard.html").read_text(), "text/html; charset=utf-8")
        if self.path == "/health":
            return self._send(200, json.dumps({"ok": True}), "application/json")
        return self._send(404, json.dumps({"error": "not found"}), "application/json")


if __name__ == "__main__":
    run_engine()
    print(f"[citation-integrity] serving monitor on :{PORT}")
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
