import os, threading, time, asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
from bot import build_app, resume_workers, code_watcher_thread, seed_accounts

PORT = int(os.environ.get("PORT", 10000))

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/debug/adlog"):
            self._debug_adlog(); return
        if self.path.startswith("/debug/adlog"):
            self._debug_adlog(); return
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

    def _debug_adlog(self):
        from pathlib import Path as _P
        p = _P("/tmp/ad_debug.log")
        txt = p.read_text(encoding="utf-8") if p.exists() else "(empty)"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(txt.encode("utf-8"))

    def _debug_ad(self):
        import storage, json, threading, time as _t
        def _run():
            from farm_engine import fetch_initdata_sync
            from ad_watcher import watch_one_ad
            accs = storage.list_accounts()
            if not accs: return
            a = accs[0]
            logs = []
            def log(m): logs.append(str(m))
            try:
                idata = fetch_initdata_sync(a["session"])
                if not idata:
                    logs.append("fetch_initdata FAIL")
                else:
                    storage.update_account(a["id"], init_data=idata, init_ts=int(_t.time()))
                    from urllib.parse import urlparse, parse_qs
                    qs = parse_qs(urlparse(self.path).query)
                    tname = qs.get("task", ["Adsgram"])[0]
                    r = watch_one_ad(idata, log=log, max_wait=60, task_name=tname)
                    logs.append("RESULT: " + json.dumps(r, ensure_ascii=False, default=str))
            except Exception as e:
                logs.append("ERR: " + str(e)[:200])
            with open("/tmp/ad_debug.log", "w") as fp:
                fp.write(chr(10).join(logs))
        threading.Thread(target=_run, daemon=True).start()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status":"started"}')

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

