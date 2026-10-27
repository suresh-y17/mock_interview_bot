# PUSH_TO_GITHUB.md — uploading this project to your GitHub

Everything here is copy-paste. Two routes: **Route 1** uses the ready-to-push zip I gave
you (recommended — it keeps all 19 commits and the history), **Route 2** uses plain
upload of files (no git needed, but you lose the history).

Before you start, confirm the destination repo exists: **https://github.com/suresh-y17/mock_interview_bot**

---

## What you were given

| File | What it is | Use it how |
|---|---|---|
| **`interviewloop-github-ready.zip`** | The whole project **including its git history** (19 commits, broker `main` branch, remote already set) | Route 1. Unzip → `git push`. That's it. |
| `mock_interview_bot.zip` | Same code without `.git` | Copy files manually, or drag-drop into GitHub |
| `standalone.html` | The entire app as one file | Double-click. Needs no install, no server |
| `GO_LIVE.md` | Beginner guide to running it locally and deploying | Read this after the push |
| `PROJECT_FILES.md` | Every file in one copy-pasteable document | For rebuilding the repo by hand |

The zip contains **no database, no virtual environment, no secrets** — I checked. The
database is created automatically on first run, so shipping it would be wrong.

---

# Route 1 — The ready-to-push zip (recommended)

## Step 1 — Unzip it

Unzip `interviewloop-github-ready.zip`. You get a folder named `mock_interview_bot`.

Open a terminal and go into it:

```
cd path/to/mock_interview_bot
```

> **Trick for beginners:** type `cd ` (with a space), then drag the folder from your file
> manager into the terminal window, then press Enter. It fills in the path for you.

## Step 2 — Confirm the history came with it

```
git log --oneline
```

You should see 19 lines, newest first. The top one mentions `docs: add GO_LIVE.md`.
**If you see "not a git repository",** stop and use Route 2 instead — your unzip tool may
have dropped the hidden `.git` folder. (On macOS, press **Cmd + Shift + .** to reveal
hidden folders; on Windows, File Explorer → View → tick "Hidden items".)

## Step 3 — Point it at your repo

The zip's remote is already `https://github.com/suresh-y17/mock_interview_bot.git`. If
your username is different, correct it now:

```
git remote set-url origin https://github.com/YOUR-USERNAME/mock_interview_bot.git
```

Check what it says:

```
git remote -v
```

## Step 4 — Push

```
git push -u origin main
```

You'll be asked for a **Username** and **Password**:

- **Username:** your GitHub username
- **Password:** **NOT your GitHub password.** GitHub has refused account passwords for
  git operations since 2021. You must paste a Personal Access Token.

### Making the token (2 minutes)

1. GitHub → click your avatar (top right) → **Settings**
2. Left menu, scroll to the bottom → **Developer settings**
3. **Personal access tokens** → **Tokens (classic)**
4. **Generate new token** → **Generate new token (classic)**
5. Fill in:
   - **Note:** `interviewloop-push`
   - **Expiration:** `30 days`
   - **Scopes:** tick **`repo`** (the whole group). Nothing else is needed.
6. **Generate token** at the bottom
7. Copy the `ghp_…` string **immediately** — GitHub never shows it again

Paste it as the password. A terminal shows nothing while you paste — that's normal, just
press Enter.

> **This token is a password.** Don't commit it, screenshot it, or paste it into a chat.
> Revoke it when you're done: same page → the token → **Delete**.

### Optional: stop typing the token every time

```
git config --global credential.helper store
```

This saves it in plain text on **your** machine only (`~/.git-credentials`). Convenient on a
personal laptop; don't do it on a shared computer.

## Step 5 — Confirm it worked

```
git status
```

You want: `Your branch is up to date with 'origin/main'.`

Then open **https://github.com/suresh-y17/mock_interview_bot** in your browser. You
should see `README.md` rendered on the page, the folder list, and "19 commits" in the
top bar.

## Step 6 — The master/main trap (if the repo looks empty on GitHub)

**Symptom:** the push reported success, the terminal is happy, but the GitHub page shows
an empty repo with only a README you didn't write.

**Cause:** GitHub expects a branch called `master`, your work is on `main` (or the
reverse). The code is *there*, GitHub is just looking at the wrong branch.

**Fix, in order of preference:**

1. On GitHub go to **Settings** → **Branches** → change **Default branch** to `main`
2. If `main` isn't offered, push it explicitly:
   ```
   git push -u origin main:master
   ```
3. Or rename locally and push again:
   ```
   git branch -M main
   git push -u origin main
   ```

I hit exactly this while testing your package against a stand-in remote — the code
uploaded fine and the clone came back empty. It is the single most common "my push
worked but GitHub is blank" cause.

## Step 7 — Making changes later

```
git add .
git commit -m "describe what changed"
git push
```

If Render is connected (see `GO_LIVE.md`, Part B), that push automatically redeploys your
live site about a minute later.

---

# Route 2 — No git at all (drag and drop)

Use this if git isn't installed or Route 1 failed.

## Option 2a — GitHub's web uploader

1. Unzip `mock_interview_bot.zip` (the one **without** `.git`)
2. Go to your repo → **Add file** → **Upload files**
3. Open the unzipped folder, select everything, drag it into the browser
4. **Important exclusions:** skip `.venv`, `venv`, `__pycache__`, and `mockinterview.db`
   if they appear. `.gitignore` already covers them, but the uploader ignores that file.
5. Scroll down → **Commit changes**

Repeat for subfolders if the uploader refuses a large batch. This is tedious but works.

## Option 2b — Turn a plain folder into a repo and push it

If you have the code as a normal folder (no `.git`) and git installed:

```
cd path/to/mock_interview_bot
git init
git branch -M main
git remote add origin https://github.com/suresh-y17/mock_interview_bot.git
git add .
git commit -m "Initial commit: InterviewLoop mock interview bot"
git push -u origin main
```

`git add .` respects `.gitignore`, so the database and virtual environment are skipped
automatically.

> **If the push is rejected** with `updates were rejected because the remote contains work
> that you do not have locally`, the repo already has commits. Either clone it fresh and
> copy your files in, or force your version with:
> ```
> git push -u origin main --force
> ```
> Only force-push a repo **you** own and **only** when you don't mind replacing what's
> there. Never on a shared repo.

---

# Verifying the upload is complete

After pushing, check these six files exist on GitHub. If any is missing, the deploy will
fail later:

| File | Why it matters |
|---|---|
| `requirements.txt` | The host installs dependencies from this |
| `run.sh` | The host's start command |
| `Procfile` | Tells Render/Railway how to start the app |
| `render.yaml` | Lets Render configure everything in one click |
| `app/main.py` | The FastAPI application |
| `static/voice.html` + `static/voice.js` | The voice interview UI |

I tested exactly this: pushed the package to a stand-in remote, cloned it back into an
empty folder, created a fresh virtual environment, ran `bash run.sh`, and got
`200` on `/`, `/text`, `/api/health` and `/api/companies` with 65 questions seeded.

**What should NOT be on GitHub:**

- `mockinterview.db` — a database of test data; it regenerates on first run
- `.venv/` — thousands of files, specific to your machine
- `.env` — **secrets.** If you ever commit this, treat the key inside as compromised and
  rotate it.

`.gitignore` already handles all three. You only need to worry if you used Route 2a.

---

# Troubleshooting

| Message | Cause | Fix |
|---|---|---|
| `fatal: could not read Username for 'https://github.com'` | No token, or you pressed Enter at the prompt | Step 4 — make a token, paste it as the password |
| `Authentication failed` | Pasted your account password, or the token lacks the `repo` scope | New token with `repo` ticked |
| `remote: Repository not found` | Typo in the URL, or the repo doesn't exist yet | Check `git remote -v`; create the repo on GitHub first |
| `Updates were rejected... remote contains work` | The repo already has commits (e.g. a README made at creation) | Clone it and copy files in, or `--force` **only** on your own repo |
| Push works but GitHub shows an empty repo | The `master` / `main` mismatch | Step 6 |
| `git: command not found` | Git isn't installed | Windows: https://git-scm.com/download/win · Mac: `brew install git` · Linux: `sudo apt install git` |
| `error: src refspec main does not match any` | You have no commits yet | `git add . && git commit -m "Initial commit"` first |
| `Permission denied (publickey)` | You're using an SSH URL without SSH keys set up | Use the `https://` URL instead, with a token |

---

# After the push: make it live

You now have code on GitHub but nothing running publicly yet. Two choices, both in
**`GO_LIVE.md`**:

- **Part A** — run it on your own laptop at `http://localhost:8000` (do this first; errors
  are easier to read locally)
- **Part B** — deploy to Render for free, giving you a public `https://` link anyone can
  open. Since `render.yaml` is in the repo, this is: Render dashboard → **New +** →
  **Blueprint** → pick the repo → **Apply**. Nothing to type.

Remember that the live link is `https://`, which is required anyway — browsers only allow
microphone access on `localhost` or HTTPS.
