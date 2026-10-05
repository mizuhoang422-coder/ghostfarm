import os, threading, time
from http.server import BaseHTTPRequestHandler, HTTPServer
from bot import build_app, resume_workers, code_watcher_thread, seed_accounts
PORT = int(os.environ.get("PORT", 10000))
class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
        self.wfile.write(b"ghostfarm ok")
    def log_message(self, *a, **k): pass
def run_http():
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()
if __name__ == "__main__":
    threading.Thread(target=run_http, daemon=True).start()
    app = build_app()
    seed_accounts()
    resume_workers()
    code_watcher_thread()
    import subprocess
    def _delayed_scan():
        time.sleep(20)
        try:
            subprocess.Popen(["python", "scan_once.py"])
        except Exception as e:
            print(f"[scan boot] {e}")
    threading.Thread(target=_delayed_scan, daemon=True).start()
    app.run_polling(allowed_updates=["message","callback_query"], drop_pending_updates=True)

