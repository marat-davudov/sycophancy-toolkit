#!/usr/bin/env python3
"""Convert conversation files listed in conversation_files.csv into one normalised messages CSV.

Usage:
  extract_messages.py [FILES_CSV] [--output-dir DIR] [--tool SUBSTRING ...] [--no-actions]

Defaults: FILES_CSV = output/conversations/conversation_files.csv, DIR = its directory.
Writes DIR/conversation_messages.csv with columns:
  conversation_id, tool, role, turn_index, timestamp, model, text
and DIR/extraction_report.json (counts per tool and every skipped file with the reason).

Assistant rows end with an "[Actions]" block summarising edits, commands and lookups the
assistant made in that exchange, unless --no-actions is given.

Supported formats (see references/formats.md): VS Code-family chatSessions JSON and JSONL,
and GitHub Copilot CLI events.jsonl. Everything else is skipped and reported, never guessed.
"""
import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

csv.field_size_limit(sys.maxsize)

NO_RESPONSE = "[No assistant text captured in the exported response.]"
FIELDS = ["conversation_id", "tool", "role", "turn_index", "timestamp", "model", "text"]
MAX_ACTIONS = 30
SNIPPET_CHARS = 200
LOOKUP_HINTS = ("read", "view", "find", "search", "list", "grep", "glob", "rg", "fetch", "usages",
                "geterrors", "problems", "changes")
# Edits made by these VS Code tools also appear as textEditGroup items, which carry the inserted text.
VSCODE_EDIT_TOOLS = ("replacestring", "multireplace", "createfile", "applypatch", "editnotebook", "insertedit")
SKIP_TOOLS = ("manage_todo_list", "stop_bash", "report_intent")


def iso(value):
    """Epoch milliseconds or ISO string -> local 'YYYY-MM-DDTHH:MM:SS' ('' if unknown)."""
    try:
        if isinstance(value, (int, float)) and value > 0:
            dt = datetime.fromtimestamp(value / 1000)
        elif isinstance(value, str) and value:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            dt = dt.astimezone() if dt.tzinfo else dt
        else:
            return ""
    except (ValueError, OverflowError, OSError):
        return ""
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def clip(text, n=SNIPPET_CHARS):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1] + "…"


def uri_path(uri):
    if isinstance(uri, dict):
        return uri.get("fsPath") or uri.get("path") or ""
    if isinstance(uri, str):
        parsed = urlparse(uri)
        return unquote(parsed.path) if parsed.scheme == "file" else uri
    return ""


def plain(message):
    """Tool messages are markdown; turn '[](file:///x/y.py)' links into the path."""
    text = message.get("value", "") if isinstance(message, dict) else message if isinstance(message, str) else ""
    return re.sub(r"\[([^\]]*)\]\((file://[^)]+)\)", lambda m: m.group(1) or uri_path(m.group(2)), text)


class Actions:
    """Ordered, compact log of what the assistant did during one exchange."""

    def __init__(self):
        self.items = []  # (text, call_id) or ("\0edit", path)
        self.edits = {}  # path -> [count, inserted text]
        self.lookups = []

    def add(self, text, call_id=None):
        self.items.append((text, call_id))

    def lookup(self, target):
        self.lookups.append(clip(target, 60))

    def edit(self, path, inserted=""):
        if path not in self.edits:
            self.edits[path] = [0, ""]
            self.items.append(("\0edit", path))
        entry = self.edits[path]
        entry[0] += 1
        if len(entry[1]) < SNIPPET_CHARS and inserted:
            entry[1] += (" " if entry[1] else "") + inserted

    def render(self, failed=frozenset()):
        lines = []
        if self.lookups:
            shown = ", ".join(dict.fromkeys(self.lookups[:5]))
            more = f" (+{len(self.lookups) - 5} more)" if len(self.lookups) > 5 else ""
            lines.append(f"inspected {len(self.lookups)} item(s): {shown}{more}")
        for text, ref in self.items:
            if text == "\0edit":
                count, inserted = self.edits[ref]
                label = f"edited {ref}" + (f" ({count} edits)" if count > 1 else "")
                lines.append(label + (f": {clip(inserted)}" if inserted.strip() else ""))
            else:
                lines.append(text + (" (failed)" if ref is not None and ref in failed else ""))
        if len(lines) > MAX_ACTIONS:
            lines = lines[:MAX_ACTIONS] + [f"… and {len(lines) - MAX_ACTIONS} more action(s)"]
        return lines


def is_lookup(name):
    name = name.lower()
    return any(h in name for h in LOOKUP_HINTS)


def render_vscode_response(items, with_actions):
    """Return (assistant text, action lines) for one VS Code request's response list."""
    text, chunk, actions, tool_edits = [], [], Actions(), []
    has_edit_groups = any(isinstance(i, dict) and i.get("kind") in ("textEditGroup", "notebookEditGroup")
                          for i in items or [])
    for it in items if isinstance(items, list) else []:
        if not isinstance(it, dict):
            continue
        kind = it.get("kind")
        if kind is None:
            if isinstance(it.get("value"), str):
                chunk.append(it["value"])
            continue
        if chunk:  # consecutive markdown items are one streamed block
            text.append("".join(chunk))
            chunk = []
        if not with_actions:
            continue
        if kind == "toolInvocationSerialized":
            tool = it.get("toolId") or "tool"
            if any(t in tool.lower() for t in SKIP_TOOLS):
                continue
            if has_edit_groups and any(t in tool.lower() for t in VSCODE_EDIT_TOOLS):
                continue
            data = it.get("toolSpecificData")
            if isinstance(data, dict) and data.get("kind") == "terminal":
                cmd = data.get("commandLine")
                if isinstance(cmd, dict):
                    cmd = cmd.get("original") or cmd.get("userEdited") or cmd.get("toolEdited")
                if isinstance(cmd, str) and cmd.strip():
                    actions.add(f"ran `{clip(cmd)}`")
                    continue
            message = plain(it.get("pastTenseMessage")) or plain(it.get("invocationMessage"))
            if is_lookup(tool):
                actions.lookup(message or tool)
            else:
                actions.add(f"{tool}: {clip(message)}" if message else tool)
        elif kind in ("textEditGroup", "notebookEditGroup"):
            inserted = []
            for group in it.get("edits") or []:
                for e in group if isinstance(group, list) else [group]:
                    if isinstance(e, dict) and isinstance(e.get("text"), str):
                        inserted.append(e["text"])
            actions.edit(uri_path(it.get("uri")) or "unknown file", " ".join(inserted).strip())
        elif kind == "workspaceEdit":
            actions.add(f"workspace edit ({len(it.get('edits') or [])} change(s))")
    if chunk:
        text.append("".join(chunk))
    return "\n\n".join(t.strip() for t in text if t.strip()), actions.render()


def vscode_exchanges(session, with_actions):
    fallback = iso(session.get("lastMessageDate")) or iso(session.get("creationDate"))
    exchanges = []
    for req in session["requests"]:
        if not isinstance(req, dict):
            continue
        msg = req.get("message")
        text, actions = render_vscode_response(req.get("response"), with_actions)
        exchanges.append({
            "user": msg.get("text", "") if isinstance(msg, dict) else "",
            "assistant": text, "actions": actions,
            "timestamp": iso(req.get("timestamp")) or fallback, "model": req.get("modelId") or "",
        })
    return exchanges


def extract_vscode_chat(path, with_actions):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("requests"), list):
        raise ValueError("no 'requests' list")
    return data.get("sessionId") or path.stem, vscode_exchanges(data, with_actions), 0


def replay_mutation_log(path):
    """VS Code chatSessions/*.jsonl: line 0 is the initial state (kind 0); later lines set a
    value at path k (kind 1), append v to the array at k after truncating it at i (kind 2),
    or delete k (kind 3). Returns (state, number of lines that could not be applied)."""
    state, bad = None, 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            op = json.loads(line)
        except ValueError:
            bad += 1  # usually a partially written last line
            continue
        kind, keys = op.get("kind"), op.get("k") or []
        if kind == 0:
            state = op.get("v")
            continue
        if state is None or not keys:
            bad += 1
            continue
        try:
            parent = state
            for k in keys[:-1]:
                parent = parent[k]
            last = keys[-1]
            if kind == 1:
                parent[last] = op.get("v")
            elif kind == 2:
                try:
                    arr = parent[last]
                except (KeyError, IndexError):
                    arr = None
                if not isinstance(arr, list):
                    arr = []
                    parent[last] = arr
                if isinstance(op.get("i"), int):
                    del arr[op["i"]:]
                arr.extend(op.get("v") or [])
            elif kind == 3:
                del parent[last]
            else:
                bad += 1
        except (KeyError, IndexError, TypeError):
            bad += 1
    return state, bad


def extract_vscode_chat_jsonl(path, with_actions):
    state, bad = replay_mutation_log(path)
    if not isinstance(state, dict) or not isinstance(state.get("requests"), list):
        raise ValueError("no 'requests' list after replaying the log")
    return state.get("sessionId") or path.stem, vscode_exchanges(state, with_actions), bad


def cli_tool_action(actions, data):
    name = data.get("toolName") or "tool"
    args = data.get("arguments")
    call_id = data.get("toolCallId")
    if name in SKIP_TOOLS:
        return
    if not isinstance(args, dict):
        args = {"input": args} if isinstance(args, str) else {}
    if name == "bash":
        actions.add(f"ran `{clip(args.get('command', ''))}`", call_id)
    elif name == "edit":
        actions.edit(args.get("path") or "unknown file", str(args.get("new_str") or ""))
    elif name == "create":
        actions.edit(args.get("path") or "unknown file", str(args.get("file_text") or ""))
    elif name == "apply_patch":
        patch = next((v for v in args.values() if isinstance(v, str)), "")
        files = re.findall(r"^\*\*\* (?:Add|Update|Delete) File: (.+)$", patch, re.M)
        for f in files or ["(patch)"]:
            actions.edit(f.strip(), "")
    elif is_lookup(name):
        target = args.get("path") or args.get("pattern") or args.get("url") or args.get("query") or args.get("paths") or name
        actions.lookup(f"{name} {target}" if target != name else name)
    else:
        detail = next((args[k] for k in ("description", "message", "intent", "query", "skill", "prompt", "input")
                       if isinstance(args.get(k), str) and args[k].strip()), "")
        actions.add(f"{name}: {clip(detail)}" if detail else name, call_id)


def extract_copilot_cli_events(path, with_actions):
    exchanges, failed, bad = [], set(), 0
    current = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except ValueError:
            bad += 1
            continue
        data = event.get("data") or {}
        kind = event.get("type")
        if kind == "user.message":
            current = {"user": data.get("content", ""), "parts": [], "actions": Actions(),
                       "timestamp": iso(event.get("timestamp")), "model": ""}
            exchanges.append(current)
        elif current is None:
            continue
        elif kind == "assistant.message":
            content = data.get("content")
            if isinstance(content, str) and content.strip():
                current["parts"].append(content)
            current["model"] = data.get("model") or current["model"]
        elif kind == "tool.execution_start" and with_actions:
            cli_tool_action(current["actions"], data)
        elif kind == "tool.execution_complete" and data.get("success") is False:
            failed.add(data.get("toolCallId"))
    return path.parent.name, [
        {"user": e["user"], "assistant": "\n\n".join(e["parts"]), "actions": e["actions"].render(failed),
         "timestamp": e["timestamp"], "model": e["model"]}
        for e in exchanges
    ], bad


def pick_extractor(path):
    if path.suffix == ".json":
        return extract_vscode_chat
    if path.suffix == ".jsonl" and path.name == "events.jsonl":
        return extract_copilot_cli_events
    if path.suffix == ".jsonl" and path.parent.name == "chatSessions":
        return extract_vscode_chat_jsonl
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files_csv", nargs="?", default="output/conversations/conversation_files.csv")
    ap.add_argument("--output-dir", help="default: directory of FILES_CSV")
    ap.add_argument("--tool", action="append", default=[],
                    help="only include rows whose tool contains this text (case-insensitive); repeatable")
    ap.add_argument("--no-actions", action="store_true",
                    help="omit the [Actions] summary of edits, commands and lookups from assistant rows")
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

    skipped, conversations, malformed = [], {}, 0
    for row in rows:
        path = Path(row["path"])
        extractor = pick_extractor(path)
        if not extractor:
            skipped.append({"tool": row["tool"], "path": str(path),
                            "reason": f"unsupported format ({path.suffix or 'no extension'})"})
            continue
        try:
            cid, exchanges, bad = extractor(path, not args.no_actions)
        except (OSError, ValueError, UnicodeDecodeError) as e:
            skipped.append({"tool": row["tool"], "path": str(path), "reason": f"unreadable: {e}"})
            continue
        malformed += bad
        if not exchanges:
            skipped.append({"tool": row["tool"], "path": str(path), "reason": "no messages"})
            continue
        new = {"tool": row["tool"], "path": str(path), "exchanges": exchanges}
        old = conversations.get(cid)
        if old:
            # The same session can exist in both .json and .jsonl form; keep the fuller copy.
            kept, dropped = (new, old) if len(exchanges) > len(old["exchanges"]) else (old, new)
            conversations[cid] = kept
            skipped.append({"tool": dropped["tool"], "path": dropped["path"],
                            "reason": f"duplicate conversation id {cid} (kept {kept['path']})"})
            continue
        conversations[cid] = new

    stats, by_tool = Counter(), {}
    out_path = out_dir / "conversation_messages.csv"
    with out_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, FIELDS)
        writer.writeheader()
        for cid, conv in conversations.items():
            tool = conv["tool"]
            t = by_tool.setdefault(tool, {"conversations": 0, "exchanges": 0, "without_assistant_text": 0,
                                          "first": "", "last": ""})
            t["conversations"] += 1
            stats["conversations"] += 1
            for n, ex in enumerate(conv["exchanges"], 1):
                body = ex["assistant"].strip()
                actions_only = not body and bool(ex["actions"])
                if ex["actions"]:
                    body = (body + "\n\n" if body else "") + "[Actions]\n" + "\n".join(f"- {a}" for a in ex["actions"])
                common = {"conversation_id": cid, "tool": tool, "timestamp": ex["timestamp"], "model": ex["model"]}
                writer.writerow({**common, "role": "User", "turn_index": 2 * n - 1, "text": ex["user"]})
                writer.writerow({**common, "role": "Assistant", "turn_index": 2 * n, "text": body or NO_RESPONSE})
                stats["exchanges"] += 1
                stats["exchanges_without_assistant_text"] += not body
                stats["exchanges_with_actions_only"] += actions_only
                t["exchanges"] += 1
                t["without_assistant_text"] += not body
                if ex["timestamp"]:
                    t["first"] = min(t["first"] or ex["timestamp"], ex["timestamp"])
                    t["last"] = max(t["last"], ex["timestamp"])

    report = {**stats, "actions_included": not args.no_actions, "malformed_lines_skipped": malformed,
              "by_tool": by_tool, "skipped_files": skipped}
    (out_dir / "extraction_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"conversations: {stats['conversations']}, exchanges: {stats['exchanges']} "
          f"({stats['exchanges_without_assistant_text']} without captured assistant text)")
    for tool, t in by_tool.items():
        print(f"  {tool}: {t['conversations']} conversations, {t['exchanges']} exchanges, "
              f"{t['first'][:10] or '?'} -> {t['last'][:10] or '?'}")
    if malformed:
        print(f"skipped {malformed} malformed line(s) inside otherwise readable files")
    for reason, n in Counter("duplicate conversation id" if s["reason"].startswith("duplicate")
                             else s["reason"].split(":")[0] for s in skipped).items():
        print(f"skipped {n} file(s): {reason}")
    print(f"wrote {out_path} and {out_dir / 'extraction_report.json'}")
    if not stats["conversations"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
