# Supported conversation formats

`extract_messages.py` chooses an extractor from the file name and extension (`pick_extractor`). Every extractor returns, per exchange: user text, assistant text, a list of actions, an ISO timestamp (local time) and a model id.

## VS Code-family chat sessions (`*.json`)

Found by `find_conversations.py` at `<AppData>/{Code,Code - Insiders,VSCodium,Cursor,Windsurf}/User/workspaceStorage/*/chatSessions/*.json`.

- One file per session; conversation id is `sessionId` (falls back to the file name).
- `requests[]` is the list of exchanges, in order. Timestamp: `requests[].timestamp` (epoch ms), falling back to the session's `lastMessageDate`/`creationDate`. Model: `requests[].modelId`.
- User text: `requests[].message.text`.
- Assistant text: in `requests[].response[]`, items **without** a `kind` key that carry a string `value` (markdown). Consecutive items are one streamed block and are concatenated; blocks separated by other items are joined with a blank line.
- Actions, from items with a `kind`: `toolInvocationSerialized` (terminal tools give `toolSpecificData.commandLine`; other tools give `pastTenseMessage`/`invocationMessage`; read/search/list tools are counted as lookups), `textEditGroup`/`notebookEditGroup` (file `uri` and inserted `edits[][].text`, merged per file), `workspaceEdit`. Edit-tool invocations are dropped when edit groups are present, because the groups carry the content. `thinking`, references, `undoStop` and progress items are ignored.
- Sessions with an empty `requests` list are skipped as "no messages".

## VS Code-family chat sessions (`*.jsonl`, mutation log)

Same location, newer format. Each line is an operation; replaying them gives the same session object as the `.json` format, which is then read as above.

- `{"kind": 0, "v": state}`: initial session state.
- `{"kind": 1, "k": path, "v": value}`: set the value at `path` (list of keys and indexes).
- `{"kind": 2, "k": path, "v": [items], "i": n}`: truncate the array at `path` to `n` items if `i` is present, then append `v`.
- `{"kind": 3, "k": path}`: delete.
- Lines that don't parse (typically a half-written last line) or don't apply are skipped and counted in `malformed_lines_skipped`.

## GitHub Copilot CLI (`events.jsonl`)

Found at `~/.copilot/session-state/<session-id>/events.jsonl`; conversation id is the `<session-id>` directory name.

- One JSON event per line with `type`, `data` and an ISO `timestamp`.
- `user.message` starts an exchange; text is `data.content`.
- `assistant.message` events until the next user message are joined; only non-empty `data.content` is kept. Model: `data.model`.
- Actions: `tool.execution_start` (`data.toolName`, `data.arguments`): `bash` commands, `edit`/`create` (path plus inserted text), `apply_patch` (files named in the patch), lookups (`view`, `rg`, `glob`, ...) and other tools with their description. A `tool.execution_complete` with `success: false` marks the action as failed.

## Not supported (skipped and reported)

`state.vscdb` (SQLite), Copilot CLI `history-session-state` files, Claude Code / Codex / Gemini CLI / Continue / Zed / Ollama / LM Studio / Open WebUI / Aider stores, and any other file type. Inspect a real file before adding an extractor.

## Output schema

`conversation_messages.csv`: `conversation_id, tool, role, turn_index, timestamp, model, text`. `role` is `User` or `Assistant`; `turn_index` counts messages within a conversation from 1 (user = odd, assistant = even). Assistant `text` may end with an `[Actions]` block of `- ` lines.
