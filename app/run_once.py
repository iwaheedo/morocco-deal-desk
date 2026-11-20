#!/usr/bin/env python3
"""Analyse one listing from the command line or from GitHub Actions.

    python3 app/run_once.py "<Mubawab link>"

On GitHub the link comes from LISTING_URL (the Run workflow box) or from ISSUE_TEXT (the title and
body of the issue the web page opens). Saves the run (runs/), the result page (results/) and the
property record, writes the page to the run's summary, and leaves a one-line outcome in
.run_note.md for the reply posted on the issue.
"""
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pipeline  # noqa: E402
import report_md  # noqa: E402

SITE = "https://iwaheedo.github.io/morocco-deal-desk/"


def out(text):
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write(text + "\n")
    print(text)


def note(text):
    (pipeline.DATA / ".run_note.md").write_text(text + "\n", encoding="utf-8")


def main():
    url = (os.environ.get("LISTING_URL") or (sys.argv[1] if len(sys.argv) > 1 else "")).strip()
    if not url:   # opened from the web page: find the link in the issue text; nothing else in it is used
        m = re.search(r"https?://[^\s<>\"')\]]+", os.environ.get("ISSUE_TEXT") or "")
        url = m.group(0) if m else ""
    try:
        run = pipeline.analyse_url(url, say=lambda m: print("…", m, flush=True))
    except pipeline.Refusal as e:
        out("## Could not analyse that link\n\n%s\n\nLink given: `%s`" % (e, url[:300]))
        note("Could not analyse that link. %s" % e)
        pipeline.log_failure(url, str(e))
        sys.exit(1)
    rec = run["record"]
    title = "%s — %s" % (rec.get("title"), (rec.get("verdict") or "").upper())
    env = os.environ.get("GITHUB_ENV")
    if env:
        with open(env, "a", encoding="utf-8") as f:
            f.write("RUN_TITLE=%s\nRESULT_FILE=%s\n" % (re.sub(r"[\r\n]+", " ", title), run["result_file"]))
    fx, m = run["fx_home"], run["metrics"]
    note("**%s**\n\nThe video's way: %+d a month. Checked: %+d a month (in %s).\n\n[Open the deal desk](%s) · [full page](../blob/main/%s)"
         % (title, round(m["v_profit"] / fx), round(m["c_profit"] / fx), run["home_currency"], SITE, run["result_file"].replace(" ", "%20")))
    out(report_md.render(run))
    print("\nSaved:", run["result_file"])


if __name__ == "__main__":
    main()
