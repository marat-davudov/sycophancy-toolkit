---
name: sycophancy-audit
description: End-to-end sycophancy audit of the user's own past AI coding conversations - finds the chat history on this machine, extracts it to CSV, scores it for sycophancy, and reports the findings. Use when the user asks to audit, analyse or check their AI assistant conversations for sycophancy in one go, without supplying a CSV.
compatibility: Requires uv (or Python 3.9+) and read access to the user's home directory. Delegates scoring to subagents when available.
metadata:
  version: "2.0"
---

# Sycophancy audit (orchestrator)

Runs two skills in order and keeps the user informed between them. Do the work through those skills; don't reimplement their steps here.

## Steps

1. **Output location.** Use what the user already said; otherwise extraction goes to `output/conversations/` and the run to a new `output/runs/<timestamp>/`. Check that the current directory's `.gitignore` covers `output/` (or that it isn't a git repo); if not, tell the user and offer a different folder. Include the Aider scan only if they use Aider. Skip to step 3 if the user gave a CSV.
2. **Extract**: use the `conversation-extraction` skill. Stop and tell the user if it finds zero conversations, or if the only tools found are unsupported formats.
3. **Choose the scope in one question**, using the per-tool counts and date ranges from extraction. Scoring costs one model pass per transcript. If there are more than ~50 conversations or ~1000 exchanges, offer concrete options, for example: the 25 most recent, the last 30 days, one tool, or everything (with counts). Otherwise just proceed with everything. The answer maps directly onto `prepare` flags (`--limit`, `--since`, `--tool`); don't write ad hoc selection scripts.
4. **Analyse**: use the `sycophancy-analysis` skill on that CSV with the chosen flags: prepare, plan-batches, score batches in parallel, validate until clean, recheck (10 or more conversations), aggregate.
5. **Report** (concise), from `summary.md`: the headline; the main prompting habit; the top incidents with a one-line reason each; caveats (sources not extracted, turns with no captured reply, validation warnings, agreement); and links to `summary.md`, `summary.csv` and `conversations.csv`.

## Rules

- Everything stays local under `output/` (owner-only, gitignored) or the folder the user names. Chat content is private: do not paste it into the report beyond brief quotes needed to explain a finding.
- Never modify the source conversation files or the user's input CSV.
- If a step fails, report the failure and what was completed; do not substitute guessed data.
- Each run gets its own folder, so re-runs never overwrite earlier results. To finish an interrupted run, re-run `plan-batches` on the same folder.

## Example prompts

- "Audit my past AI chats for sycophancy."
- "Check my Copilot and VS Code conversations for sycophancy, write results to ~/audit."
- "Analyse /path/to/messages.csv for sycophancy." (skips extraction)
