#!/usr/bin/env python3
"""Locate past AI assistant conversation stores on this machine (read-only, local only).

Usage:
  find_conversations.py              # known locations + aider history scan of ~
  find_conversations.py --no-aider   # skip the slower home-directory scan
  find_conversations.py --output-dir /some/dir   # default: ./output/conversations

Writes conversation_files.csv (tool, path, size_bytes, modified) and summary.json.
"""
import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path

HOME = Path.home()
DEFAULT_OUTPUT_DIR = Path("output") / "conversations"
if sys.platform == "darwin":
    APPDATA = HOME / "Library/Application Support"
elif sys.platform.startswith("win"):
    APPDATA = Path(os.environ.get("APPDATA", HOME / "AppData/Roaming"))
else:
    APPDATA = Path(os.environ.get("XDG_CONFIG_HOME", HOME / ".config"))

VSCODE_LIKE = ["Code", "Code - Insiders", "VSCodium", "Cursor", "Windsurf"]

# (tool, path, glob pattern for conversation files)
TARGETS = [
    ("GitHub Copilot CLI", HOME / ".copilot/session-state", "**/*.jsonl"),
    ("GitHub Copilot CLI", HOME / ".copilot/history-session-state", "**/*.json*"),
    ("Claude Code", HOME / ".claude/projects", "**/*.jsonl"),
    ("Claude Code", HOME / ".claude/history.jsonl", None),
    ("Claude Desktop", APPDATA / "Claude", "**/*.json"),
    ("ChatGPT Desktop", APPDATA / "com.openai.chat", "**/*"),
    ("Codex CLI", HOME / ".codex/sessions", "**/*.jsonl"),
    ("Gemini CLI", HOME / ".gemini/tmp", "**/*.json*"),
    ("Continue", HOME / ".continue/sessions", "*.json"),
    ("Zed AI", APPDATA / "Zed/conversations", "*"),
    ("Zed AI", HOME / ".local/share/zed/conversations", "*"),
    ("Ollama", HOME / ".ollama/history", None),
    ("Open WebUI", HOME / ".open-webui", "**/*.db"),
    ("LM Studio", HOME / ".lmstudio/conversations", "**/*.json"),
    ("LM Studio", HOME / ".cache/lm-studio/conversations", "**/*.json"),
]

for app in VSCODE_LIKE:
    base = APPDATA / app / "User"
    TARGETS.append((f"{app} chat sessions", base / "workspaceStorage", "*/chatSessions/*.json"))
    TARGETS.append((f"{app} editor state (chat DB)", base / "globalStorage", "state.vscdb"))
    TARGETS.append((f"{app} Cline/Roo/Continue tasks", base / "globalStorage", "*/tasks/*/api_conversation_history.json"))


def collect(path: Path, pattern):
    if not path.exists():
        return []
    if path.is_file():
        return [path]
    try:
        return [p for p in path.glob(pattern or "*") if p.is_file()]
    except OSError:
        return []


def scan_aider(root: Path, max_depth=5):
    skip = {"node_modules", ".git", "Library", ".Trash", "venv", ".venv", "__pycache__", ".cache"}
    hits = []
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        if len(Path(dirpath).parts) - root_depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames if d not in skip]
        for f in filenames:
            if f in (".aider.chat.history.md", ".aider.input.history"):
                hits.append(Path(dirpath) / f)
    return hits


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.0f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-aider", action="store_true")
    ap.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR),
                    help="where to write results (default: output/conversations in the current directory)")
    args = ap.parse_args()

    results = {}
    for tool, path, pattern in TARGETS:
        files = collect(path, pattern)
        if files:
            results.setdefault((tool, str(path)), []).extend(files)
    if not args.no_aider:
        hits = scan_aider(HOME)
        if hits:
            results[("Aider", str(HOME))] = hits

    report = []
    for (tool, loc), files in sorted(results.items()):
        stats = []
        for f in files:
            try:
                st = f.stat()
                stats.append((st.st_mtime, st.st_size))
            except OSError:
                pass
        if not stats:
            continue
        newest = max(s[0] for s in stats)
        oldest = min(s[0] for s in stats)
        fmt = lambda t: time.strftime("%Y-%m-%d", time.localtime(t))
        entry = {
            "tool": tool, "location": loc, "files": len(stats),
            "size_bytes": sum(s[1] for s in stats),
            "oldest": fmt(oldest), "newest": fmt(newest),
            "examples": [str(f) for f in files[:3]],
        }
        report.append(entry)
        print(f"{tool}\n  {loc}\n  {entry['files']} files, {human(entry['size_bytes'])}, "
              f"{entry['oldest']} -> {entry['newest']}")
        for ex in entry["examples"]:
            print(f"    e.g. {ex}")
        print()

    if not report:
        print("No known AI conversation stores found.")
        return

    out = Path(args.output_dir).expanduser()
    out.mkdir(parents=True, exist_ok=True, mode=0o700)
    out.chmod(0o700)  # results contain private paths; owner-only
    csv_path = out / "conversation_files.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["tool", "path", "size_bytes", "modified"])
        for (tool, _), files in sorted(results.items()):
            for f in files:
                try:
                    st = f.stat()
                except OSError:
                    continue
                modified = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(st.st_mtime))
                w.writerow([tool, str(f), st.st_size, modified])
    (out / "summary.json").write_text(json.dumps(report, indent=2))
    print(f"Wrote {csv_path} and {out / 'summary.json'}")


if __name__ == "__main__":
    main()
