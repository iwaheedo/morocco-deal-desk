# Morocco deal desk

**Open it on any device: https://iwaheedo.github.io/morocco-deal-desk/**

Paste a Mubawab listing, get the video's "analyse the deal" sum beside a checked one, and keep every run.
This repository is public: it holds the buyer profile used for the sums (no name) and every analysis.

## Analyse a flat from any device

1. Open the page above, paste the Mubawab link, press **Analyse the deal**.
2. GitHub opens with the request filled in. Press the green button (you need to be signed in as the owner; other people's requests are ignored).
3. About two minutes later the result appears on the page. It is also saved in [`results/`](results/).

The other way in: **Actions → Analyse a property → Run workflow**, paste the link.

## Read past results

[`results/`](results/) — one page per run, named by date, area and verdict, newest at the bottom.
The spreadsheet from each run is attached to that run under **Artifacts**.

## On the Mac

Double-click `Start deal desk.command` for the full page with history. Runs made there are pushed here
automatically, and runs made from GitHub appear there.

## What is in here

| | |
|---|---|
| `app/` | The page, the automatic analysis (`pipeline.py`) and the result writer |
| `engine/` | The model, spreadsheet builder, Mubawab reader and sourced assumptions (copy of the Claude skill) |
| `data/` | Anonymous Airbnb price points for Rabat (rounded position, bedrooms, price), used for local comparables |
| `profile.json` | Who is buying and on what loan terms. Edit `overrides` to change an assumption |
| `properties/`, `runs/`, `results/` | One record per flat, one file per run, one readable page per run |
| `reports/` | Longer write-ups done with Claude |
| `research/` | The verification notes behind the assumptions |

Analysis, not legal, tax or financial advice.
