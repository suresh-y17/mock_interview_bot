# GO_LIVE.md — putting InterviewLoop on the internet, step by step

Written for someone who has never deployed anything. Nothing here assumes you know
what a server, a port, or a build command is. Every command is copy-paste.

There are **two paths**. Read this table, pick one, and skip the other.

| | Path A — Local | Path B — Live on the internet |
|---|---|---|
| **What it means** | Runs on *your* laptop, at `http://localhost:8000` | Runs on a computer owned by a hosting company, at a real `https://` link |
| **Who can open it** | Only you | Anyone you send the link to |
| **Cost** | Free | Free |
| **Time** | ~10 minutes | ~15 minutes |
| **Needs** | Python installed | A GitHub account + a Render account |
| **Link works when your laptop is off?** | No | Yes |

> **Path A first.** If the app does not run on your own laptop, it will not run on a
> server either, and every error is easier to read locally. Do Path A, confirm the
> voice interview works, then do Path B.

---

# PART 0 — Words you'll see, in plain English

You do not need to memorise these. Skim them so the steps below don't feel alien.

| Word | What it actually means |
|---|---|
| **Terminal** (or *command line*, *shell*, *console*) | A window where you type commands instead of clicking. On Windows it's "PowerShell" or "Command Prompt". On Mac it's "Terminal". |
| **Repository / repo** | A folder of code that git keeps track of, with its full history. |
| **Git** | The tool that records changes to your folder. |
| **GitHub** | A website that stores repos online so other computers (like a host) can download them. |
| **Commit** | A saved snapshot of your files. |
| **Push** | Upload your commits to GitHub. |
| **Localhost** | "This computer, right here." `localhost:8000` = port 8000 on your own machine. |
| **Port** | A numbered door on a computer. A web server sits behind one. Ours is `8000`. |
| **Deploy** | Copy your code to someone else's computer and start it running there. |
| **Build command** | The command a host runs to install your dependencies. |
| **Start command** | The command a host runs to actually launch your app. |
| **Dependency** | A library your code needs. Ours are listed in `requirements.txt`. |
| **Environment variable** | A setting passed to a program from outside the code, like an API key. |
| **Cold start** | On a free host, your app goes to sleep when nobody uses it. The next visit takes ~30–60s to wake up. Normal. |

---

# PART A — Run it on your own laptop

## Step A1 — Check whether Python is installed

Open your terminal and type this exact line, then press Enter:

```
python3 --version
```

You should see something like `Python 3.12.7`.

- **If you see a version:** good, continue to A2.
- **If you see "command not found" or the Microsoft Store opens:** try `python --version` instead. If that also fails, install Python:
  - **Windows:** go to https://www.python.org/downloads/ and run the installer. **On the very first screen, tick the box that says "Add python.exe to PATH"** — this is the single most common beginner mistake. Then close and reopen the terminal.
  - **Mac:** run `brew install python` (or download from python.org).
  - **Linux:** `sudo apt install python3 python3-venv python3-pip`

## Step A2 — Get the code onto your laptop

Pick **one** of these three, whichever matches what you have.

**Option 1 — If you already pushed to GitHub** (do Path B step B1 first, then come back):

```
git clone https://github.com/suresh-y17/mock_interview_bot.git
cd mock_interview_bot
```

**Option 2 — If you downloaded `mock_interview_bot.zip`:**

Unzip it. You get a folder called `mock_interview_bot`. Then:

```
cd path/to/mock_interview_bot
```

(drag the folder into the terminal window after typing `cd ` and it fills the path for you)

**Option 3 — If someone sent you the single file `standalone.html`:**

You can **double-click it** and it opens in your browser. No Python at all. Skip to
Part C to learn the limitations of that mode.

## Step A3 — Create a virtual environment

A "virtual environment" is a private box for this project's libraries so they can't
break anything else on your laptop. Create it:

```
python3 -m venv .venv
```

Now **activate** it. This is the part people forget — it must be done **every time you
open a new terminal** to work on this project.

- **Mac / Linux:**
  ```
  source .venv/bin/activate
  ```
- **Windows (PowerShell):**
  ```
  .venv\Scripts\Activate.ps1
  ```
- **Windows (Command Prompt):**
  ```
  .venv\Scripts\activate.bat
  ```

Your prompt should now start with `(.venv)`. That is how you know it worked.

> **Windows error: "running scripts is disabled on this system"?** Run this once, then retry:
> ```
> Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
> ```

## Step A4 — Install the dependencies

```
pip install -r requirements.txt
```

Three small libraries. Takes under a minute. If `pip` is not found, use `python3 -m pip install -r requirements.txt`.

## Step A5 — Start it

```
bash run.sh
```

On Windows, if `bash` is not recognised, use these three lines instead:

```
python -m app.db
python -m uvicorn app.main:app --reload --port 8000
```

The first time, you will see the database being created and filled with questions:

```
Seeded database at .../mockinterview.db
  questions: 65
  reviews  : 23
INFO:     Uvicorn running on http://0.0.0.0:8000
```

**That last line means it is running. Leave this terminal window open.** Closing it
stops the server.

## Step A6 — Open it and run one interview

In **Chrome** or **Edge**, go to:

```
http://localhost:8000
```

Checklist:

1. The page shows a glowing circle and a **Start the interview** button.
2. Open "Who are you interviewing with?" and enter your name.
3. Click **Start** → the browser asks for microphone permission → click **Allow**.
4. The interviewer speaks a question. When it stops, the bar says *Listening to you*.
5. **Answer out loud.** When you stop talking for ~1.7 seconds, your answer sends itself.
6. It replies, asks the next question, and gives you a report at the end.

To stop the server: go back to the terminal and press **Ctrl + C**.

> **Everything is a spoken command.** Say "repeat", "skip", "hint", "send it", or
> "end the interview". There are no buttons during the interview — that is the point.

### Must-know: Voice only works in the right place

| Situation | Speaks? | Listens? |
|---|---|---|
| Chrome/Edge at `http://localhost:8000` | ✅ | ✅ |
| Chrome/Edge at `https://…` (Path B) | ✅ | ✅ |
| Safari 16+ | ✅ | ✅ (iPhone may need a tap per turn) |
| **Firefox** | ✅ | ❌ — no speech recognition at all |
| Chrome at `http://192.168.x.x` (a raw IP) | ✅ | ❌ |

Browsers only allow the microphone on **`localhost`** or **`https://`**. That rule is
theirs, not the app's. If you open the app via a LAN IP, the page will show a warning
explaining exactly this.

---

# PART B — Put it live on the internet (free)

## How this works, in one picture

```
your laptop  --git push-->  GitHub  --Render reads it-->  a server runs your app  -->  https://your-app.onrender.com
```

You never touch the server. You push code; Render notices and updates the live site.

## Step B1 — Put the code on GitHub

You need a free GitHub account: https://github.com/signup

**If you already have the code running locally (Part A), the repo is already a git
repository.** Check:

```
git status
```

Then push it:

```
git remote add origin https://github.com/YOUR-USERNAME/mock_interview_bot.git
git branch -M main
git push -u origin main
```

Replace `YOUR-USERNAME`. When asked for a password, paste a **Personal Access Token**,
not your GitHub password (GitHub stopped accepting passwords in 2021):

1. GitHub → your avatar → **Settings** → **Developer settings** (bottom of left menu)
2. **Personal access tokens** → **Tokens (classic)** → **Generate new token (classic)**
3. Note: `interviewloop`, Expiration: `30 days`, tick the **`repo`** checkbox
4. **Generate token**, then copy the `ghp_…` string immediately — it is shown once
5. Paste it when git asks for a password

> The token is a password. Never paste it into a file, a screenshot, or a chat. Revoke
> it when you're done (same page → Delete).

**No git installed?** Alternative with zero commands: on GitHub click **New repository**,
name it `mock_interview_bot`, don't add a README, click **Create**. On the empty repo page
click **"uploading an existing file"**, then drag in everything **except** the `.venv`
folder and `mockinterview.db`. The database is created automatically on the server.

## Step B2 — Create the Render account

1. Go to https://render.com and click **Get Started** / **Sign Up**
2. Choose **Sign up with GitHub** (one less password to manage)
3. Authorise Render to see your repositories. If asked to pick repos, you can grant
   "All repositories" or just `mock_interview_bot`
4. **No credit card is required for the free plan**

## Step B3 — Deploy using the blueprint (recommended — nothing to type)

This project includes a file called `render.yaml` that already describes the whole
service. Render reads it and fills in every field for you.

1. In the Render dashboard, click **+ New** (top right)
2. Click **Blueprint**
3. Find `mock_interview_bot` in the list and click **Connect**
4. Render shows a service named **interviewloop** with the plan **Free** already chosen
5. Click **Apply** / **Create**
6. Watch the log. You'll see `pip install -r requirements.txt`, then the seeding lines
   (`questions: 65`), then `Uvicorn running on http://0.0.0.0:10000`
7. When the status badge turns **Live**, your URL appears at the top:
   `https://interviewloop-xxxx.onrender.com`

That's it. Open the link and you are on the internet.

### If Blueprint is not offered — create a Web Service by hand

Same result, four fields to fill:

| Field | What to enter |
|---|---|
| **Source** | your `mock_interview_bot` repo |
| **Language / Runtime** | **Python 3** |
| **Branch** | `main` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `bash run.sh` |
| **Instance Type** | **Free** |
| **Health Check Path** (under Advanced) | `/api/health` |

Click **Create Web Service**. Nothing else is required — no database to add, no
environment variables, no API keys. The app seeds its own database on first boot.

## Step B4 — Check it actually works

Open your live URL and run the A6 checklist. Two things specific to the live site:

**1. The first visit will be slow.** On the free plan, Render puts your app to sleep
after 15 minutes with no visitors. The next visit takes 30–60 seconds to wake it. You
will see a blank page or a spinner — **wait, don't refresh in a panic.** The second
visit is instant.

**2. Microphone permission.** The link is `https://`, so the mic works. Click **Allow**
when Chrome asks. If you accidentally clicked Block: click the padlock icon in the
address bar → Microphone → Allow → reload.

## Step B5 — Making changes later

This is the whole loop:

```
git add .
git commit -m "describe what you changed"
git push
```

Render notices the push and redeploys automatically in about a minute. No clicking.

## Optional — turn on the smarter AI interviewer

By default the interviewer uses a built-in rule engine. It works offline, costs nothing,
and needs no signup. It scores answers, reacts, and asks follow-up questions — but its
wording is template-based.

If you want it to generate its own follow-up questions in natural language, plug in an
OpenAI-compatible API key. **This is optional; do not do it on your first deploy.**

1. Get a key from https://platform.openai.com/api-keys (or Groq / OpenRouter — any
   OpenAI-compatible endpoint, including a local Ollama)
2. Render dashboard → your service → **Environment** → **Add Environment Variable**
3. Add `OPENAI_API_KEY` = your key. Optionally `LLM_BASE_URL` and `LLM_MODEL`.
4. Save. Render restarts the service by itself.

Never put the key in code, in `render.yaml`, or on GitHub. Environment variables exist
precisely so secrets stay out of the repository.

---

# PART C — The zero-install option: one HTML file

There is a file called `standalone.html` in the project. **Double-click it.** It opens
in your browser and the whole app runs — no Python, no terminal, no internet.

Useful when: you want to demo on a friend's laptop, your college machine blocks
installs, or you're offline.

| Works | Doesn't work |
|---|---|
| Voice interview, all 65 questions, both learning loops | Any data survives a browser-cache wipe |
| Scoring, follow-ups, the full report | Sharing a link with someone else (it's a file) |
| Saves progress in the browser automatically | Anything needing the Python server |

You **cannot** upload this file to GitHub Pages and call it live — see the next section
for why.

---

# PART D — When it doesn't work

Find your symptom. Each one is a real failure with a real cause.

### "python3: command not found"
Python isn't installed, or isn't on your PATH. Part A1. On Windows, reinstall and tick
**"Add python.exe to PATH"**.

### "No module named uvicorn" / "No module named fastapi"
The virtual environment isn't active, or dependencies aren't installed. Part A3 then A4.
Your prompt must show `(.venv)`.

### "Address already in use" / port 8000 is busy
Something else is using port 8000. Either stop it, or use another port:
```
PORT=8000 python3 -m uvicorn app.main:app --port 8001
```
then open `http://localhost:8001`.

### The page loads but every action shows an error, or `/api/health` says `ok: false`
The database didn't get created. Fix it:
```
rm mockinterview.db
python3 -m app.db
```
(Windows: `del mockinterview.db`). Then restart.

### The interviewer is silent
1. Is it Chrome or Edge? Firefox cannot listen (it can still speak).
2. Is the URL `localhost` or `https://`? A raw IP will not get the microphone.
3. Click the padlock in the address bar → Microphone → **Allow** → reload.
4. Is the tab muted? Right-click the tab and check.
5. Your system volume / output device.

### The page says "microphone blocked"
Same as above — browser site permissions. Allow, then reload.

### It hears me but never sends my answer
It sends after a pause. The lobby has a **"How long a pause means I'm done"** setting —
choose *Quick — 1.2 seconds* if you speak in short bursts. Say **"send it"** to send
immediately.

### It keeps hearing itself / answers its own question
That would be an echo-guard failure. Check that you're on the latest code (`git pull`).
Also: use headphones, or lower your speaker volume — a loud speaker can leak into the mic.

### Render build fails with "No open ports detected"
The start command must bind to the port Render provides. Use exactly `bash run.sh` — it
already handles `${PORT}`. If you typed a start command by hand, make sure it ends with
`--port $PORT`, not `--port 8000`.

### Render says "Live" but the page is blank
Wait 60 seconds — it's the cold start (Part B4). If it persists, open
`https://your-url.onrender.com/api/health`. If that returns `"ok": true`, the server is
fine and it's a browser cache issue: hard-reload with **Ctrl + Shift + R**.

### I pushed to GitHub but Render shows the old version
Check the **Events** tab in Render — the deploy may still be running, or it failed.
Failed builds do not replace a working site; the old one keeps serving.

### "fatal: could not read Username" when pushing
GitHub needs a Personal Access Token, not your password. Part B1.

---

# PART E — Cheat sheet

```
# first-time setup on a new laptop
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
bash run.sh                        # -> http://localhost:8000

# everyday: come back later  (cd into the project folder and activate first)
source .venv/bin/activate
bash run.sh

# stop the server
Ctrl + C

# reset the database to a clean seed
rm mockinterview.db && python3 -m app.db

# rebuild the offline single-file app
python3 standalone/build.py

# run the tests
python3 tests/test_scoring.py

# deploy a change
git add . && git commit -m "my change" && git push
```

| URL | What it is |
|---|---|
| `http://localhost:8000` | The voice interview (the main app) |
| `http://localhost:8000/text` | Text chat version, for keyboards |
| `http://localhost:8000/api/health` | Server health, as JSON |
| `http://localhost:8000/docs` | Auto-generated API reference |
| `standalone.html` | The whole app in one file — double-click it |

---

# Two honest warnings

**1. The free database is temporary.** The app stores data in a single SQLite file on the
server. On Render's free plan, that file is wiped whenever the service rebuilds or
redeploys. Questions and reviews are re-seeded automatically, so nothing breaks — but
past session history will vanish. For a portfolio project that is completely fine. If you
ever need persistence, that means moving to Render Postgres, which is a real (if
moderate) project of its own.

**2. Chrome's speech recognition is not private.** It sends your recorded audio to
Google's servers to transcribe it. The app itself stores nothing — audio never touches
the server or the database — but the transcription is a cloud service. If you need
genuinely offline speech, that requires a different engine (Whisper or Vosk running
locally), which is a significant change. For a mock-interview practice tool, the
tradeoff is reasonable; just know it, and don't record anything sensitive.
