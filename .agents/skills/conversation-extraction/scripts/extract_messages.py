#!/usr/bin/env python3
"""Convert conversation files listed in conversation_files.csv into one normalised messages CSV.

Usage:
  extract_messages.py [FILES_CSV] [--output-dir DIR] [--tool SUBSTRING ...]

Defaults: FILES_CSV = output/conversations/conversation_files.csv, DIR = its directory.
Writes DIR/conversation_messages.csv with columns:
  conversation_id, tool, role, turn_index, text
and DIR/extraction_report.json (counts and every skipped file with the reason).

Supported formats (see references/formats.md): VS Code-family chatSessions JSON and
GitHub Copilot CLI events.jsonl. Everything else is skipped and reported, never guessed.
"""
import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)

NO_RESPONSE = "[No assistant text captured in the exported response.]"
FIELDS = ["conversation_id", "tool", "role", "turn_index", "text"]


def extract_vscode_chat(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("requests"), list):
        raise ValueError("no 'requests' list")
    cid = data.get("sessionId") or path.stem
    exchanges = []
    for req in data["requests"]:
        msg = req.get("message")
        user = msg.get("text", "") if isinstance(msg, dict) else ""
        response = req.get("response")
        parts = []
        if isinstance(response, list):
            # Plain markdown chunks have no "kind"; tool calls, references, edits etc. do.
            parts = [i["value"] for i in response
                     if isinstance(i, dict) and "kind" not in i
                     and isinstance(i.get("value"), str) and i["value"].strip()]
        exchanges.append((user, "\n\n".join(parts)))
    return cid, exchanges


def extract_copilot_cli_events(path):
    cid = path.parent.name
    exchanges = []
    user, parts = None, []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        data = event.get("data") or {}
        kind = event.get("type")
        if kind == "user.message":
            if user is not None:
                exchanges.append((user, "\n\n".join(parts)))
            user, parts = data.get("content", ""), []
        elif kind == "assistant.message" and user is not None:
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content)
    if user is not None:
        exchanges.append((user, "\n\n".join(parts)))
    return cid, exchanges


def pick_extractor(path):
    if path.suffix == ".json":
        return extract_vscode_chat
    if path.suffix == ".jsonl" and path.name == "events.jsonl":
        return extract_copilot_cli_events
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files_csv", nargs="?", default="output/conversations/conversation_files.csv")
    ap.add_argument("--output-dir", help="default: directory of FILES_CSV")
    ap.add_argument("--tool", action="append", default=[],
                    help="only include rows whose tool contains this text (case-insensitive); repeatable")
    args = ap.parse_args()

    files_csv = Path(args.files_csv).expanduser()
    if not files_csv.is_file():
        sys.exit(f"{files_csv} not found. Run find_conversations.py first.")
    out_dir = Path(args.output_dir).expanduser() if args.output_dir else files_csv.parent
    out_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    out_dir.chmod(0o700)  # chat content is private; owner-only

    with files_csv.open(newline="", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    wanted = [t.lower() for t in args.tool]
    if wanted:
        rows = [r for r in rows if any(t in r["tool"].lower() for t in wanted)]

    skipped, seen, stats = [], set(), Counter()
    out_path = out_dir / "conversation_messages.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, FIELDS)
        writer.writeheader()
        for row in rows:
            path = Path(row["path"])
            extractor = pick_extractor(path)
            if not extractor:
                skipped.append({"path": str(path), "reason": f"unsupported format ({path.suffix or 'no extension'})"})
                continue
            try:
                cid, exchanges = extractor(path)
            except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as e:
                skipped.append({"path": str(path), "reason": f"unreadable: {e}"})
                continue
            if not exchanges:
                skipped.append({"path": str(path), "reason": "no messages"})
                continue
            if cid in seen:
                skipped.append({"path": str(path), "reason": f"duplicate conversation id {cid}"})
                continue
            seen.add(cid)
            stats["conversations"] += 1
            for n, (user, assistant) in enumerate(exchanges, 1):
                writer.writerow({"conversation_id": cid, "tool": row["tool"], "role": "User", "turn_index": 2 * n - 1, "text": user})
                writer.writerow({"conversation_id": cid, "tool": row["tool"], "role": "Assistant", "turn_index": 2 * n,
                                 "text": assistant or NO_RESPONSE})
                stats["exchanges"] += 1
                stats["exchanges_without_assistant_text"] += not assistant

    report = {**stats, "skipped_files": skipped}
    (out_dir / "extraction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"conversations: {stats['conversations']}, exchanges: {stats['exchanges']} "
          f"({stats['exchanges_without_assistant_text']} without captured assistant text)")
    for reason, n in Counter(s["reason"].split(":")[0] for s in skipped).items():
        print(f"skipped {n} file(s): {reason}")
    print(f"wrote {out_path} and {out_dir / 'extraction_report.json'}")
    if not stats["conversations"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
