---
name: conversation-extraction
description: Finds past AI coding-assistant conversations stored on this machine (VS Code/Cursor/Windsurf chats, Copilot CLI, Claude Code, Codex, Gemini CLI, Aider and others) and converts supported ones into a normalised messages CSV (one row per message). Use when the user wants to locate, list, export or extract their past AI chat history, or needs a conversations CSV for analysis.
compatibility: Requires uv (or Python 3.9+) and read access to the user's home directory; scripts use only the standard library and never send data anywhere.
metadata:
  version: "1.0"
---

# Conversation extraction

Two read-only, local steps. Commands run from the repository root. Output defaults to `output/conversations/` in the current directory, created owner-only; it contains local paths and private chat content, so it must be gitignored. Use `--output-dir DIR` for another location.

## Steps

1. **Locate** conversation stores and list every file:
   `uv run .agents/skills/conversation-extraction/scripts/find_conversations.py [--no-aider] [--output-dir DIR]`
   Writes `conversation_files.csv` (`tool, path, size_bytes, modified`) and `summary.json`. Use `--no-aider` to skip the slow home-directory scan unless the user uses Aider. Only default locations are checked; to add a tool, append to `TARGETS` in the script.
2. **Extract** messages from the listed files:
   `uv run .agents/skills/conversation-extraction/scripts/extract_messages.py [output/conversations/conversation_files.csv] [--tool SUBSTRING ...] [--no-actions] [--output-dir DIR]`
   Writes `conversation_messages.csv` (`conversation_id, tool, role, turn_index, timestamp, model, text`) and `extraction_report.json` (counts per tool with date ranges, and every skipped file with its tool and reason). Use `--tool` (repeatable, case-insensitive) when the user wants only some tools. Assistant rows end with an `[Actions]` block summarising the edits, commands and lookups made in that exchange, so scoring can see what was implemented; `--no-actions` leaves it out.
3. **Report**: conversations and exchanges per tool with date ranges, anything skipped (see below), and the output paths. The printed summary is enough; `output/` is gitignored, so editor search tools won't find these files. Open them by path.

## Supported formats and limits

See [formats.md](references/formats.md). Supported: VS Code-family `chatSessions/*.json` and `chatSessions/*.jsonl` (the newer mutation-log format), and Copilot CLI `events.jsonl`. When a session exists in both VS Code formats, the copy with more exchanges is kept. Files in other formats (e.g. `state.vscdb`, Claude Code, Codex) are located in step 1 but skipped in step 2 and listed in `extraction_report.json`; tell the user which tools are affected rather than guessing a format. Add a new format by writing an extractor and registering it in `pick_extractor`, after inspecting a real file's structure (print keys and types, not content).

Exchanges with neither assistant text nor actions get the text `[No assistant text captured in the exported response.]`; report how many.

## Rules

- Never modify or delete the source conversation files.
- Don't print or quote conversation content in the report beyond what the user asks for; it is private.
- Keep outputs under `output/` or the folder the user names; never commit them.
- Stop and report if step 2 finds zero conversations.

## Next step

Hand `conversation_messages.csv` to the `sycophancy-analysis` skill. Its column names (including `timestamp`, `tool` and `model`, used for selection and grouping) are auto-detected.
