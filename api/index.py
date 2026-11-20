"""The deal desk as one hosted function (Vercel): the same API the Mac app serves.

GET  /api/profile            buyer and loan terms
GET  /api/history            every entry, newest first
GET  /api/run?id=…           one entry in full
POST /api/analyse {"url"}    analyse a Mubawab listing and keep the result

Entries are kept in Vercel Blob storage (BLOB_READ_WRITE_TOKEN). Without it they last only until the
server restarts, and /api/profile says so.
"""
import json
import os
import shutil
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("DEAL_DESK_WORK") or "/tmp/deal-desk")
if not (WORK / "profile.json").exists():          # fresh server: lay out a writable copy of the small data files
    (WORK / "properties").mkdir(parents=True, exist_ok=True)
    (WORK / "runs").mkdir(exist_ok=True)
    shutil.copy2(ROOT / "profile.json", WORK / "profile.json")
    for f in (ROOT / "properties").glob("*.json"):
        if json.loads(f.read_text(encoding="utf-8")).get("origin") != "auto":
            shutil.copy2(f, WORK / "properties" / f.name)   # hand-refined analyses travel with the code
os.environ["DEAL_DESK_DATA"] = str(WORK)
os.environ.setdefault("TZ", "Europe/London")   # entries are stamped in UK time, as on the Mac
time.tzset()
os.environ["DEAL_DESK_DIRECT"] = "1"
sys.path.insert(0, str(ROOT / "app"))
import pipeline  # noqa: E402

TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN")
BLOB = "https://blob.vercel-storage.com"
_cache = {}


def _blob(method, path, body=None, headers=None):
    req = urllib.request.Request(BLOB + path, data=body, method=method,
                                 headers=dict({"authorization": "Bearer %s" % TOKEN, "x-api-version": "7"}, **(headers or {})))
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def keep(run):
    _cache[run["run_id"]] = run
    if TOKEN:
        _blob("PUT", "/runs/%s.json" % run["run_id"], json.dumps(run, ensure_ascii=False).encode("utf-8"),
              {"x-content-type": "application/json", "x-add-random-suffix": "0", "x-allow-overwrite": "1",
               "x-vercel-blob-access": "public", "x-cache-control-max-age": "60"})


def all_runs():
    runs = {}
    for folder in (ROOT / "runs", WORK / "runs"):            # entries that shipped with the code, and this server's own
        for f in folder.glob("*.json"):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                runs[r["run_id"]] = r
            except (ValueError, KeyError):
                pass
    if TOKEN:
        listed = _blob("GET", "/?" + urllib.parse.urlencode({"prefix": "runs/", "limit": "1000"})).get("blobs", [])
        todo = [b for b in listed if Path(b["pathname"]).stem not in _cache]

        def fetch(b):
            with urllib.request.urlopen(b["url"], timeout=20) as r:
                return json.loads(r.read().decode("utf-8"))

        with ThreadPoolExecutor(8) as ex:
            for r in ex.map(fetch, todo):
                _cache[r["run_id"]] = r
    runs.update(_cache)
    return runs


class handler(BaseHTTPRequestHandler):
    def _send(self, code, body):
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parts = urllib.parse.urlsplit(self.path)
        q = urllib.parse.parse_qs(parts.query)
        try:
            if parts.path.endswith("/profile"):
                self._send(200, dict(pipeline.profile_summary(), keeps_history=bool(TOKEN)))
            elif parts.path.endswith("/history"):
                rows = [pipeline.row_of(r) for r in all_runs().values()]
                self._send(200, sorted(rows, key=lambda r: r["at"], reverse=True))
            elif parts.path.endswith("/run"):
                run = all_runs().get((q.get("id") or [""])[0])
                self._send(200 if run else 404, run or {"error": "That entry is no longer on file."})
            elif parts.path.endswith("/progress"):
                self._send(200, {"msg": "", "busy": False})
            else:
                self._send(404, {"error": "Not found"})
        except Exception as e:
            self._send(500, {"error": "The site hit a problem: %s" % e})

    def do_POST(self):
        if not urllib.parse.urlsplit(self.path).path.endswith("/analyse"):
            return self._send(404, {"error": "Not found"})
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
        except ValueError:
            return self._send(400, {"error": "The request was not valid JSON."})
        url = str(body.get("url") or "")[:600]
        try:
            run = pipeline.analyse_url(url)
            keep(run)
            self._send(200, run)
        except pipeline.Refusal as e:
            try:
                keep(pipeline.log_failure(url, str(e)))
            except Exception:
                pass
            self._send(422, {"error": str(e)})
        except Exception as e:
            try:
                keep(pipeline.log_failure(url, "The analysis stopped: %s" % e))
            except Exception:
                pass
            self._send(500, {"error": "The analysis stopped: %s" % e})
