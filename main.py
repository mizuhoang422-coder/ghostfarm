import os, threading, time, asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from bot import build_app, resume_workers, code_watcher_thread, seed_accounts

PORT = int(os.environ.get("PORT", 10000))

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/debug/ad"):
            self._debug_ad(); return
        if self.path.startswith("/debug/status"):
            self._debug_status(); return
        self.send_response(200); self.send_header("Content-Type","text/plain"); self.end_headers()
        self.wfile.write(b"ghostfarm ok")
    def _debug_status(self):
        import storage
        accs = storage.list_accounts()
        out = []
        for a in accs:
            out.append({
                "id": a["id"], "name": a["name"], "farm": a.get("farm_running"),
                "initData": len(a.get("init_data") or ""),
                "init_ts": a.get("init_ts"),
            })
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(__import__("json").dumps(out, ensure_ascii=False).encode())
    def _debug_ad(self):
        import storage, json, time as _t
        from farm_engine import fetch_initdata_sync
        from ad_watcher import watch_one_ad
        accs = storage.list_accounts()
        if not accs:
            self.send_response(400); self.end_headers(); return
        a = accs[0]
        logs = []
        def log(m): logs.append(str(m))
        try:
            idata = fetch_initdata_sync(a["session"])
            if not idata:
                logs.append("fetch_initdata FAIL")
                result = {"err": "no_initdata"}
            else:
                storage.update_account(a["id"], init_data=idata, init_ts=int(_t.time()))
                result = watch_one_ad(idata, log=log, max_wait=60, task_name="Adsgram")
        except Exception as e:
            result = {"err": str(e)[:200]}
        self.send_response(200); self.send_header("Content-Type","application/json"); self.end_headers()
        self.wfile.write(json.dumps({"logs": logs, "result": result}, ensure_ascii=False).encode())
    def log_message(self, *a, **k): pass

def run_http():
    HTTPServer(("0.0.0.0", PORT), H).serve_forever()

if __name__ == "__main__":
    # Set event loop cho MainThread
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # Doi instance cu tat (tranh Conflict getUpdates)
    print("[main] doi 20s cho instance cu tat...")
    time.sleep(20)

    threading.Thread(target=run_http, daemon=True).start()
    app = build_app()
    seed_accounts()
    resume_workers()
    code_watcher_thread()
    print("[main] starting bot polling...")
    app.run_polling(allowed_updates=["message","callback_query"], drop_pending_updates=True)
