#!/usr/bin/env python3
"""Local web app for the Morocco deal desk.  python3 server.py [port]   (default: $PORT, else 8791; this machine only)

GET  /                 the page
GET  /api/profile      who is buying and on what loan terms
GET  /api/history      every past run, newest first
GET  /api/run?id=…     one past run in full
GET  /api/progress     what the running analysis is doing
POST /api/analyse      {"url": "<Mubawab listing>"}  ->  the run
GET  /tracker.xlsx     the spreadsheet
"""
import json
import os
import sys
import threading
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pipeline

HERE = Path(__file__).resolve().parent
LOCK = threading.Lock()
PROGRESS = {"msg": "", "busy": False}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(parts.query)
        try:
            if parts.path in ("/", "/index.html"):
                self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
            elif parts.path == "/api/profile":
                self._send(200, pipeline.profile_summary())
            elif parts.path == "/api/history":
                pipeline.pull_if_stale()          # pick up runs made from other devices
                self._send(200, pipeline.history())
            elif parts.path == "/api/run":
                run = pipeline.load_run((q.get("id") or [""])[0])
                self._send(200 if run else 404, run or {"error": "That run is no longer on file."})
            elif parts.path == "/api/progress":
                self._send(200, PROGRESS)
            elif parts.path == "/tracker.xlsx":
                f = pipeline.DATA / "Morocco Property Tracker.xlsx"
                if f.exists():
                    self._send(200, f.read_bytes(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               {"Content-Disposition": 'attachment; filename="Morocco Property Tracker.xlsx"'})
                else:
                    self._send(404, {"error": "No spreadsheet yet. Analyse a property first."})
            else:
                self._send(404, {"error": "Not found"})
        except Exception as e:  # keep the server up; show the cause
            traceback.print_exc()
            self._send(500, {"error": "Something broke on this machine: %s" % e})

    def do_POST(self):
        if urllib.parse.urlsplit(self.path).path != "/api/analyse":
            return self._send(404, {"error": "Not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "The request was not valid JSON."})
        if not LOCK.acquire(blocking=False):
            return self._send(409, {"error": "Another analysis is still running. Wait for it to finish."})
        PROGRESS.update(msg="Starting", busy=True)
        try:
            run = pipeline.analyse_url(body.get("url"), say=lambda m: PROGRESS.update(msg=m))
            self._send(200, run)
            threading.Thread(target=pipeline.sync, kwargs={"message": "Run: %s" % (run["record"].get("title") or run["run_id"])}, daemon=True).start()
        except pipeline.Refusal as e:
            pipeline.log_failure(body.get("url"), str(e))
            self._send(422, {"error": str(e)})
            threading.Thread(target=pipeline.sync, kwargs={"message": "Entry not analysed"}, daemon=True).start()
        except Exception as e:
            traceback.print_exc()
            self._send(500, {"error": "The analysis stopped: %s" % e})
        finally:
            PROGRESS.update(msg="", busy=False)
            LOCK.release()

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.log_date_time_string(), fmt % args))


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT") or 8791)
    print("Morocco deal desk on http://127.0.0.1:%d  (Ctrl-C to stop)" % port, flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
