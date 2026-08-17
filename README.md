# Study Planner (FastAPI + PostgreSQL)

A weekly calendar planner + multi-subject syllabus tracker with real completion
history, stored in PostgreSQL and served by a FastAPI backend.

## Project structure
```
study-planner-app/
├── main.py          # FastAPI app + API routes + serves the frontend
├── models.py         # SQLAlchemy tables (events, subjects, topics)
├── schemas.py         # Pydantic request/response shapes
├── database.py        # DB connection (reads DATABASE_URL env var)
├── requirements.txt
└── static/
    └── index.html     # the whole frontend (calendar, syllabus, history)
```

## 1. Run it locally

You need Python 3.10+ and a PostgreSQL database (local or free cloud one — see below).

```bash
cd study-planner-app
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

**Get a Postgres database in 2 minutes (no local install needed):**
1. Go to https://neon.tech → sign up free → "Create a project".
2. Copy the connection string it gives you (starts with `postgresql://`).

**Set it as an environment variable, then run:**
```bash
# macOS/Linux
export DATABASE_URL="postgresql://<your-neon-connection-string>"
# Windows PowerShell
$env:DATABASE_URL="postgresql://<your-neon-connection-string>"

uvicorn main:app --reload
```

Open **http://localhost:8000** — the same server serves both the API and the UI.
Tables are created automatically on first run.

(If you'd rather run Postgres locally instead of Neon: `docker run --name pg -e POSTGRES_PASSWORD=postgres -p 5432:5432 -d postgres`,
then leave `DATABASE_URL` unset — the default in `database.py` points at that container.)

## 2. Host it free on the web

**Backend + frontend: Render.com (free tier)**

Fastest path — using the included blueprint:
1. Push this folder to a GitHub repo.
2. Go to https://render.com → New → **Blueprint** → connect your repo (it auto-detects `render.yaml`).
3. When prompted, paste your Neon `DATABASE_URL` connection string as the env var value.
4. Deploy. Render gives you a URL like `https://study-planner-xxxx.onrender.com`.

Manual path (if you skip the blueprint):
1. Push this folder to a GitHub repo.
2. Go to https://render.com → New → Web Service → connect your repo.
3. Settings:
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. Add an environment variable `DATABASE_URL` = your Neon connection string from step 1.
5. Deploy.

Note: I can't create the Render/Neon accounts or click "Deploy" for you — this runs from Anthropic's servers with no access to your accounts or the open internet for signups. The steps above are the fastest path I can hand you; each one is a couple of clicks.


**Database: Neon.tech (free tier)** — already set up above. Free tier gives ~0.5GB storage, which is plenty for personal planner data.

### Notes on the free tier
- Render's free web services sleep after ~15 minutes of no traffic; the first request after that takes ~30-50 seconds to wake up. Fine for personal use, just expect that delay occasionally.
- Neon's free tier also pauses when idle and wakes automatically on the next query — no action needed.
- Alternative to Render if you hit limits: Railway.app or Fly.io also have free/low-cost tiers and work the same way (same build/start commands).

## Calendar features
- **Week view** — the original hour-by-hour grid, tap-select hours → Add Task.
- **Month view** — toggle with the Week/Month buttons above the calendar. Shows a full month grid with colored dots per day; tap a day to jump into its week view.
- **Reschedule without dragging** — tap any existing task block to open Edit, where you can change its date and start/end time directly (more reliable on touchscreens than drag-and-drop).
- **Repeat weekly** — when adding a new task, check "Repeat weekly" and set how many weeks; it creates that many linked occurrences. Deleting one gives you the choice of "Delete" (just that occurrence) or "Delete future" (this one and every later occurrence in the series).

**Not included:** real-time two-way sync with your actual Google Calendar. That requires registering a Google Cloud project, OAuth consent screen, and API credentials under your own Google account — a separate setup task outside what a downloaded app can do on its own. Happy to help set that up as a follow-on if you want it.

## Password-protecting your app

The app has a real login page (not a browser popup) with a signed session cookie — you sign in once and stay logged in for 30 days.

- **Enabled automatically once you set `APP_PASSWORD`** as an environment variable. On Render: Environment tab, same place you added `DATABASE_URL` — or it's already listed in `render.yaml` if you deploy via Blueprint, so Render will prompt you for it during setup.
- Optional `APP_USERNAME` (defaults to `admin`) if you want a different username.
- Leave `APP_PASSWORD` unset and there's no login prompt at all — handy while testing locally.
- The whole app (page and API) is behind it — no one can view or edit your data without logging in.
- "Log out" link in the top-right of the app clears your session and returns you to the login page.
- To set it locally: `export APP_PASSWORD="yourpassword"` before running `uvicorn main:app --reload`.

Since it's one shared password rather than separate accounts, anyone you give it to has full access to everything — fine for "just me" or "me and a friend I trust with edit access," not meant for a public/multi-user rollout. Say the word if you want proper separate logins instead.

## Bulk-importing a syllabus (auto-segregated into subjects)

On the Syllabus Tracker tab there's a **Bulk Import** box. Paste your whole syllabus at once:

- Put a **blank line between subjects** — the first line after each blank line becomes the subject name, everything after it (until the next blank line) becomes that subject's topics.
- Or force a break anywhere with a line starting with `#` (useful if you don't want to rely on blank lines).

Example:
```
DBMS
Normalization (1NF-BCNF)
ER Diagrams
Transactions & Concurrency

SQL
Joins & Subqueries
Indexing

# Operating Systems
Process Scheduling
Deadlocks
```
This creates three subjects (DBMS, SQL, Operating Systems), each with its own checklist and progress bar.
Pasting into an existing subject name (case-insensitive match) adds topics to that subject instead of duplicating it.


- `GET /api/events?start=YYYY-MM-DD&end=YYYY-MM-DD` — events in a date range
- `POST /api/events` — create `{date, start_hour, end_hour, label, color}`
- `PUT /api/events/{id}` — update label/color/done (marking done stamps `completed_at`)
- `DELETE /api/events/{id}`
- `GET/POST /api/subjects`, `DELETE /api/subjects/{id}`
- `POST /api/subjects/{id}/topics` — bulk add `{lines: [...]}`
- `PUT /api/topics/{id}?done=true` — toggle (stamps `completed_at` for history)
- `DELETE /api/topics/{id}`
- `GET /api/history?days=30` — daily counts of completed topics/tasks
