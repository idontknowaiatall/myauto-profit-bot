"""
Tiny always-on web server for Hugging Face Spaces.
HF requires the container to listen on port 7860; an uptime monitor can also
ping it to keep the Space awake (free Spaces sleep after 48h of inactivity).
"""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

def start_health_server(port=7860):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"myauto profit bot is running")
        def log_message(self, *a):
            pass  # keep the log clean
    try:
        srv = HTTPServer(("0.0.0.0", port), Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        print(f"[WEB] health server listening on :{port}")
    except Exception as e:
        print(f"[WEB] health server failed (non-fatal): {e}")
