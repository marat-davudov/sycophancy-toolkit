# Supported conversation formats

`extract_messages.py` chooses an extractor from the file name and extension (`pick_extractor`).

## VS Code-family chat sessions (`*.json`)

Found by `find_conversations.py` at `<AppData>/{Code,Code - Insiders,VSCodium,Cursor,Windsurf}/User/workspaceStorage/*/chatSessions/*.json`.

- One file per session; conversation id is `sessionId` (falls back to the file name).
- `requests[]` is the list of exchanges, in order.
- User text: `requests[].message.text`.
- Assistant text: in `requests[].response[]`, only items **without** a `kind` key that carry a non-empty string `value` (plain markdown chunks). Items with a `kind` (tool invocations, references, edits, thinking, progress) are not conversation text and are ignored.
- Sessions with an empty `requests` list are skipped as "no messages".

## GitHub Copilot CLI (`events.jsonl`)

Found at `~/.copilot/session-state/<session-id>/events.jsonl`; conversation id is the `<session-id>` directory name.

- One JSON event per line with `type` and `data`.
- `user.message` starts an exchange; text is `data.content`.
- `assistant.message` events until the next user message are joined; only non-empty `data.content` is kept (many events carry only tool requests).

## Not supported (skipped and reported)

`state.vscdb` (SQLite), Claude Code / Codex / Gemini CLI / Continue / Zed / Ollama / LM Studio / Open WebUI / Aider stores, and any other file type. Inspect a real file before adding an extractor.

## Output schema

`conversation_messages.csv`: `conversation_id, tool, role, turn_index, text`. `role` is `User` or `Assistant`; `turn_index` counts messages within a conversation from 1 (user = odd, assistant = even).
