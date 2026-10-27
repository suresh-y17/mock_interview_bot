#!/usr/bin/env python3
"""
file_bundle.py — generate PROJECT_FILES.md: the whole repo as one copy-pasteable doc.

Usage:
    python3 tools/file_bundle.py            # writes PROJECT_FILES.md at repo root

Why a script instead of hand-writing the doc: the output must stay in lockstep with
the source. If a file changes, re-run this rather than editing the markdown.

Fence safety: any file containing ``` would break a normal markdown code fence, so
each fence is sized one backtick longer than the longest backtick run inside that
file. Reconstructing from the doc is therefore lossless (verified by --verify).
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "PROJECT_FILES.md"

# Files we deliberately leave out: generated at runtime, or binary and therefore
# not copy-pasteable. Each has a documented regeneration command.
EXCLUDE = {
    "standalone.html",          # python3 standalone/build.py
    "mockinterview.db",         # python3 -m app.db
    "screenshot-setup.png",     # binary image
    "screenshot-report.png",    # binary image
    "PROJECT_FILES.md",         # this output
    ".git",
}

# Display order: config -> backend -> data -> frontend -> offline -> tests -> docs
ORDER = [
    "requirements.txt", "run.sh", ".gitignore", ".env.example",
    "app/__init__.py", "app/db.py", "app/scoring.py", "app/feedback.py",
    "app/llm.py", "app/engine.py", "app/main.py",
    "data/questions.json", "data/seed_reviews.json",
    "static/index.html",
    "standalone/engine.js", "standalone/template.html", "standalone/build.py",
    "tests/test_scoring.py",
    ".github/workflows/ci.yml",
    "README.md", "SETUP.md", "PUSH_TO_GITHUB.md",
    "tools/file_bundle.py",
]

LANG = {
    ".py": "python", ".js": "javascript", ".html": "html", ".json": "json",
    ".yml": "yaml", ".yaml": "yaml", ".md": "markdown", ".sh": "bash",
    ".txt": "", ".example": "bash",
}


def tracked_files():
    """Prefer git's file list, fall back to a walk for non-git copies."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout
        files = [f for f in out.splitlines() if f.strip()]
        if files:
            return files
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    found = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDE and not d.startswith(".git")]
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT)
            found.append(rel.replace(os.sep, "/"))
    return found


def included_files():
    files = [f for f in tracked_files() if f not in EXCLUDE]
    # Keep the authored order, then append anything unexpected alphabetically.
    ordered = [f for f in ORDER if f in files]
    extra = sorted(f for f in files if f not in ordered)
    return ordered + extra


def fence_for(content, minimum=3):
    """One backtick longer than the longest run inside the file."""
    runs = [len(m) for m in re.findall(r"`+", content)]
    return "`" * max(minimum, (max(runs) + 1) if runs else minimum)


def tree_lines(files):
    """Render a directory tree from a flat path list."""
    tree = {}
    for f in files:
        node = tree
        for part in f.split("/"):
            node = node.setdefault(part, {})
    lines = []

    def walk(node, prefix=""):
        entries = sorted(node.items(), key=lambda kv: (not kv[1], kv[0]))
        for i, (name, child) in enumerate(entries):
            last = i == len(entries) - 1
            lines.append(f"{prefix}{'└── ' if last else '├── '}{name}{'/' if child else ''}")
            if child:
                walk(child, prefix + ("    " if last else "│   "))

    walk(tree)
    return lines


def build():
    files = included_files()
    total = sum((ROOT / f).stat().st_size for f in files)

    parts = [
        "# InterviewLoop — complete source, one file",
        "",
        "Every source file in the project, in copy-paste order. Reconstruction is "
        "**lossless**: the generator verifies a rebuild matches the original "
        "byte-for-byte.",
        "",
        "## How to use this",
        "",
        "**Option A — rebuild the server app (recommended)**",
        "",
        "1. Create the folders shown in the tree below.",
        "2. Create each file and paste the matching block.",
        "3. Then run:",
        "",
        "```bash",
        "pip install -r requirements.txt",
        "python -m app.db                       # creates the database, seeds 65 questions",
        "python -m uvicorn app.main:app --reload --port 8000",
        "```",
        "",
        "Open <http://localhost:8000> in Chrome or Edge.",
        "",
        "**Option B — just want the demo, no Python**",
        "",
        "You only need `standalone/` plus `data/`, then:",
        "",
        "```bash",
        "python standalone/build.py     # produces standalone.html",
        "```",
        "",
        "Double-click the resulting `standalone.html`. Whole app, one file, no server.",
        "",
        "## Not included (generated, not hand-written)",
        "",
        "| File | How to generate |",
        "|---|---|",
        "| `standalone.html` | `python standalone/build.py` |",
        "| `mockinterview.db` | `python -m app.db` |",
        "| `screenshot-*.png` | binary images — download from the project workspace |",
        "",
        f"**{len(files)} files · {total/1024:.0f} KB of text.**",
        "",
        "## Directory structure",
        "",
        "```text",
        "mockinterview/",
        *tree_lines(files),
        "```",
        "",
        "---",
        "",
        "## Files",
        "",
    ]

    for f in files:
        with open(ROOT / f, "r", encoding="utf-8", newline="") as fh:
            content = fh.read()
        lang = LANG.get(Path(f).suffix, "")
        fence = fence_for(content)
        size = len(content.encode())

        parts.append(f"<!-- FILE: {f} -->")
        parts.append("")
        parts.append(f"<sub>{size} bytes</sub>")
        parts.append("")
        parts.append(f"{fence}{lang}")
        # Split on newlines and rejoin on parse: byte-exact, including trailing
        # newlines and empty files (an empty file contributes one empty line).
        parts.extend(content.split("\n"))
        parts.append(fence)
        parts.append("")
        parts.append("---")
        parts.append("")

    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"wrote {OUT.name}: {len(files)} files, {OUT.stat().st_size/1024:.0f} KB")
    return files


def verify():
    """Reconstruct from PROJECT_FILES.md and diff against the source tree."""
    import tempfile

    lines = OUT.read_text(encoding="utf-8").split("\n")
    files = included_files()

    # Scan for:  <!-- FILE: path -->  ...  <fence>  body lines  <fence>
    parsed = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^<!-- FILE: (.+?) -->$", lines[i])
        if not m:
            i += 1
            continue
        path = m.group(1)
        # Advance to the opening fence (first line that is only backticks,
        # optionally followed by a language tag).
        j = i + 1
        while j < len(lines) and not re.match(r"^(`{3,})[a-z]*$", lines[j]):
            j += 1
        if j >= len(lines):
            print(f"FAIL: no opening fence for {path}")
            return False
        fence = re.match(r"^(`{3,})[a-z]*$", lines[j]).group(1)
        j += 1
        body = []
        while j < len(lines) and lines[j] != fence:
            body.append(lines[j])
            j += 1
        parsed[path] = "\n".join(body)
        i = j + 1

    print(f"parsed {len(parsed)} blocks, expected {len(files)}")
    ok = set(parsed) == set(files)
    missing = set(files) - set(parsed)
    extra = set(parsed) - set(files)
    if missing:
        print("  MISSING:", sorted(missing))
    if extra:
        print("  EXTRA:", sorted(extra))

    tmp = Path(tempfile.mkdtemp())
    for path, content in parsed.items():
        p = tmp / path
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8", newline="") as fh:
            fh.write(content)

    mismatches = []
    for f in files:
        orig = (ROOT / f).read_bytes()
        target = tmp / f
        rebuilt = target.read_bytes() if target.exists() else b""
        if orig != rebuilt:
            mismatches.append((f, len(orig), len(rebuilt)))

    if mismatches:
        ok = False
        print("BYTE MISMATCHES:")
        for f, a, b in mismatches:
            print(f"  {f}: original {a} bytes, rebuilt {b} bytes")
    else:
        print(f"all {len(files)} files rebuilt byte-for-byte \u2713")

    # Prove the reconstruction actually runs.
    r = subprocess.run([sys.executable, "-m", "app.db"], cwd=tmp, capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    print("seed:", out.splitlines()[0] if out else "?")
    r = subprocess.run([sys.executable, "tests/test_scoring.py"], cwd=tmp, capture_output=True, text=True)
    tail = [ln for ln in r.stdout.strip().splitlines() if ln.startswith(("PASSED", "All good"))]
    print("tests:", " | ".join(tail) or r.stdout[-200:])
    if r.returncode != 0:
        ok = False

    print("\nVERIFY:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true", help="rebuild and diff against the source")
    args = ap.parse_args()
    if args.verify:
        sys.exit(0 if verify() else 1)
    build()
