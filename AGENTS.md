# Sycophancy toolkit

Skills for measuring and reducing sycophancy in AI coding-assistant conversations. They live in `.agents/skills/` and follow the [Agent Skills specification](https://agentskills.io/specification). Requires [uv](https://docs.astral.sh/uv/); scripts use only the Python standard library.

## Always apply

For every user message, apply the `sycophancy-guard` skill (`.agents/skills/sycophancy-guard/SKILL.md`). It reframes loaded input (stated causes, leading questions, pushback, certainty or authority claims) into a neutral question, verifies the premise before answering, and holds or updates positions on evidence, not pressure. Skip it for mechanical commands and plain requirements.

## Skills

| Skill | Use it to |
|---|---|
| `sycophancy-guard` | Avoid sycophancy in the assistant's own replies. |
| `sycophancy-audit` | Run the whole pipeline: find your chats, extract them, score them, report. Start here. |
| `conversation-extraction` | Find AI chat history on this machine and convert it to a messages CSV. |
| `sycophancy-analysis` | Score a messages CSV against the rubric and aggregate the results. |

## Run an audit

Ask your assistant in plain language, from the repository root:

- "Audit my past AI chats for sycophancy."
- "Analyse `/path/to/messages.csv` for sycophancy." (skips extraction)
- "Extract my VS Code and Copilot conversations to a CSV." (extraction only)

The audit asks you to pick a scope (for example the 25 most recent conversations, the last 30 days, or one tool) before scoring a large set. Scoring costs one model pass per conversation.

Results go to `output/` in the current directory unless you name another folder:

- `output/conversations/`: `conversation_files.csv`, `conversation_messages.csv` and `extraction_report.json`.
- `output/runs/<timestamp>/`: one folder per scoring run, with `run.json` (selection and coverage), `transcripts/`, `analysis/` (one JSON per transcript), `validation.json`, `summary.md`, `summary.csv` (per turn) and `conversations.csv`.

`output/` is gitignored, so editor search tools skip it; open files there by path.

The scoring rubric is `.agents/skills/sycophancy-analysis/references/rubric.md`.

## Privacy

Everything runs locally and nothing is sent anywhere by the scripts. Extracted transcripts contain private chat content and local paths. `output/` is gitignored and created owner-only (`0700`); keep it that way, and never commit or share it. Don't modify the source conversation files.

## Limits

- Extraction supports VS Code-family `chatSessions/*.json` and `*.jsonl`, and Copilot CLI `events.jsonl`. Other tools (Claude Code, Codex, Gemini CLI, Aider, `state.vscdb`, and so on) are located but skipped and listed in `extraction_report.json`. See `.agents/skills/conversation-extraction/references/formats.md` to add one.
- Scores come from a model reading the transcripts, so treat them as indicative; the optional `recheck` step measures how consistent they are. Some exports lose assistant replies; those exchanges are scored as no sycophancy and counted in the report.

## Developing skills

Keep each `SKILL.md` under 500 lines with detail in `references/`, and validate after any change:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate .agents/skills/<skill-name>
```

Scripts are run as `uv run .agents/skills/<skill>/scripts/<script>.py`; each has `--help` or a usage docstring.
