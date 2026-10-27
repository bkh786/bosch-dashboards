#!/usr/bin/env python3
"""
Local Development Server for Bosch Dashboards
Emulates Vercel routing locally:
- Serves static assets (HTML, CSS, JS, SVG, JSON)
- Direct routing to /api/chat with Gemini 2.0 Flash
- Direct routing to /api/sync with SharePoint sync
- Rewrites /qc and /program cleanly
"""

import http.server
import socketserver
import urllib.parse
import json
import os
import sys

PORT = int(os.environ.get("PORT", 8000))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)
from api import chat
try:
    import sync_datasets
except ImportError:
    sync_datasets = None

class DevRequestHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, x-gemini-api-key")
        self.end_headers()

    def do_GET(self):
        # 1. API: /api/chat
        if self.path.startswith("/api/chat"):
            api_key = chat.resolve_api_key(header_key=self.headers.get("x-gemini-api-key"))
            status_data = chat.get_status_dict(api_key)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(status_data).encode("utf-8"))
            return

        # 2. API: /api/sync
        if self.path.startswith("/api/sync"):
            query = urllib.parse.urlparse(self.path).query
            params = urllib.parse.parse_qs(query)
            dataset_type = params.get('type', ['program'])[0].lower()

            if not sync_datasets:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": "sync_datasets module unavailable"}).encode("utf-8"))
                return

            try:
                if dataset_type in ('qc', 'quality'):
                    stream = sync_datasets.fetch_url(
                        sync_datasets.SHAREPOINT_QC_URL,
                        sync_datasets.QC_LOCAL_FALLBACKS,
                        "QC Tracker (xlsx)"
                    )
                    data = sync_datasets.parse_qc_dataset(stream)
                else:
                    stream = sync_datasets.fetch_url(
                        sync_datasets.SHAREPOINT_PROGRAM_URL,
                        sync_datasets.PROGRAM_LOCAL_FALLBACKS,
                        "Program Report (xlsb)"
                    )
                    data = sync_datasets.parse_program_dataset(stream)

                payload = json.dumps(data, default=str).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(payload)
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.send_header("Access-Control-Allow-Origin", "*")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode("utf-8"))
            return

        # 3. Clean URLs matching vercel.json
        if self.path in ("/qc", "/qc/"):
            self.path = "/qc.html"
        elif self.path in ("/program", "/program/", "/"):
            self.path = "/index.html"

        return super().do_GET()

    def do_POST(self):
        # 1. API: /api/chat
        if self.path.startswith("/api/chat"):
            content_length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else "{}"
            try:
                body = json.loads(raw_body)
            except Exception:
                body = {}

            api_key = chat.resolve_api_key(
                override_key=body.get("apiKey"),
                header_key=self.headers.get("x-gemini-api-key")
            )

            status_code, result = chat.process_chat_query(body, api_key)
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(result).encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()

if __name__ == "__main__":
    socketserver.TCPServer.allow_reuse_address = True
    httpd = None
    actual_port = PORT
    for p in [PORT, 8001, 8008, 8080]:
        try:
            httpd = socketserver.TCPServer(("", p), DevRequestHandler)
            actual_port = p
            break
        except OSError:
            continue
    if not httpd:
        print(f"Error: Could not bind to any port.")
        sys.exit(1)

    with httpd:
        print(f"==================================================")
        print(f"🚀 Bosch Dashboard Dev Server running at:")
        print(f"   http://localhost:{actual_port}")
        print(f"   http://localhost:{actual_port}/qc")
        print(f"   API /api/chat: http://localhost:{actual_port}/api/chat")
        print(f"   API /api/sync: http://localhost:{actual_port}/api/sync")
        print(f"==================================================")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dev server.")
