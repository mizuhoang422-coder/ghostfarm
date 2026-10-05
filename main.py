import os, threading, time, asyncio
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
    # Set event loop cho MainThread TRUOC khi run_polling
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    threading.Thread(target=run_http, daemon=True).start()
    app = build_app()
    seed_accounts()
    resume_workers()
    code_watcher_thread()
    print("[main] starting bot polling...")
    app.run_polling(allowed_updates=["message","callback_query"], drop_pending_updates=True)
