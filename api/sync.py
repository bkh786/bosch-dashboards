from http.server import BaseHTTPRequestHandler
import urllib.request
import http.cookiejar
import urllib.parse
import json
import io
import os
import sys

# Add parent directory to sys.path to access sync_datasets
parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

try:
    import sync_datasets
except ImportError:
    sync_datasets = None

class handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    def do_GET(self):
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        dataset_type = params.get('type', ['program'])[0].lower()

        if not sync_datasets:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "sync_datasets module unavailable"}).encode('utf-8'))
            return

        try:
            if dataset_type in ('qc', 'quality'):
                stream = sync_datasets.fetch_url(
                    sync_datasets.SHAREPOINT_QC_URL,
                    sync_datasets.QC_LOCAL_FALLBACKS,
                    "QC Tracker (xlsx)"
                )
                if not stream:
                    raise Exception("Failed to fetch QC dataset from SharePoint")
                data = sync_datasets.parse_qc_dataset(stream)
            else:
                stream = sync_datasets.fetch_url(
                    sync_datasets.SHAREPOINT_PROGRAM_URL,
                    sync_datasets.PROGRAM_LOCAL_FALLBACKS,
                    "Program Report (xlsb)"
                )
                if not stream:
                    raise Exception("Failed to fetch Program dataset from SharePoint")
                data = sync_datasets.parse_program_dataset(stream)

            payload = json.dumps(data, default=str).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
            self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
            self.end_headers()
            self.wfile.write(payload)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
