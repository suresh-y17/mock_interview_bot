# Setup — running InterviewLoop on your machine

Three commands. Pick your operating system below.

---

## The 3 commands (macOS / Linux)

```bash
git clone https://github.com/YOUR-USERNAME/interviewloop.git
cd interviewloop
./run.sh
```

Then open **<http://localhost:8000>** in Chrome or Edge.

`run.sh` creates the database on first run if it's missing, then starts the server.

## The 3 commands (Windows, PowerShell)

```powershell
git clone https://github.com/YOUR-USERNAME/interviewloop.git
cd interviewloop
python -m venv .venv ; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.db
python -m uvicorn app.main:app --reload --port 8000
```

Then open **<http://localhost:8000>**.

> If PowerShell blocks the activate script, run once:
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`

---

## Don't want Python at all?

Just open **`standalone.html`** by double-clicking it. It's the whole app in one file — no
server, no install, no internet. It opens in Chrome and works.

---

## What "localhost" means here

`localhost` = *your* computer. This is why the app must be started **on your machine** — a
server running anywhere else is not your localhost.

| Address | Who can reach it |
|---|---|
| `http://localhost:8000` | you, on your own machine |
| `http://127.0.0.1:8000` | same thing, written as an IP |
| `http://0.0.0.0:8000` | **not a browsable address** — it's what the server binds to. `ERR_ADDRESS_INVALID` is expected. |
| `http://<laptop-ip>:8000` | your phone on the same Wi-Fi, if the firewall allows |

---

## Verify it's working

```bash
curl http://localhost:8000/api/health
```

You should see `{"ok": true, "llm": {"mode": "offline", ...}}`.
Interactive API docs: <http://localhost:8000/docs>

## Useful commands

```bash
python tests/test_scoring.py            # 42 offline tests, no server needed
python -m app.db                        # (re)seed the database
python standalone/build.py              # rebuild the single-file offline edition
./run.sh                                # start the server
```

Reset everything back to the seeded demo state:

```bash
rm mockinterview.db && python -m app.db
```

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `ERR_ADDRESS_INVALID` | You typed `0.0.0.0:8000`. Use `localhost:8000`. |
| `Address already in use` | Something else has port 8000. Use `--port 8001` and open `localhost:8001`. |
| `ModuleNotFoundError: fastapi` | The virtualenv isn't active, or `pip install -r requirements.txt` didn't run. |
| `command not found: python` | Try `python3` (macOS/Linux). |
| Voice button does nothing | Use Chrome or Edge. Mic needs `localhost` or HTTPS — both work here. |
| Voice blocked / no permission prompt | Check the site permissions in the browser's address bar. |
| Page loads but no companies appear | The API isn't up. Check the terminal for a traceback. |
| Mic works, bot doesn't speak | Click "Voice mode: off" so it reads **on**, then start the session. |

---

## Sharing it with classmates (same Wi-Fi)

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Now `0.0.0.0` *is* useful: it means "listen on all network interfaces". Others open
`http://<your-laptop-ip>:8000` — find your IP with `ipconfig` (Windows) or `ifconfig` /
`ip addr` (macOS/Linux), and allow Python through the firewall.

Note that mic access over plain `http://` on an IP address will be blocked by browsers.
For shared voice use, put it behind HTTPS (see the deployment section of `README.md`).
