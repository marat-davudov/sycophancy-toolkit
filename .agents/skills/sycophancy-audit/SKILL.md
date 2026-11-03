---
name: sycophancy-audit
description: End-to-end sycophancy audit of the user's own past AI coding conversations - finds the chat history on this machine, extracts it to CSV, scores it for sycophancy, and reports the findings. Use when the user asks to audit, analyse or check their AI assistant conversations for sycophancy in one go, without supplying a CSV.
compatibility: Requires uv (or Python 3.9+) and read access to the user's home directory. Delegates scoring to subagents when available.
metadata:
  version: "1.0"
---

# Sycophancy audit (orchestrator)

Runs two skills in order and keeps the user informed between them. Do the work through those skills; don't reimplement their steps here.

## Steps

1. **Scope.** Take what the user already stated (tools, output folder, date range). Ask only about things that change the work and that they haven't said; otherwise use defaults: all tools, output folder `output/` in the current directory, include Aider scan only if they use Aider. Pass a user-given folder to every command as `--output-dir` / `OUT_DIR`. Before writing to the default, check that the current directory's `.gitignore` covers `output/` (or that it isn't a git repo); if not, tell the user and offer a different folder. Skip this step entirely if the user already gave a CSV and go to step 3.
2. **Extract**: use the `conversation-extraction` skill. Expect `output/conversations/conversation_messages.csv`. Stop and tell the user if it finds zero conversations, or if the only tools found are unsupported formats.
3. **Confirm size before scoring.** Scoring costs one model pass per transcript. If there are more than ~50 conversations or ~1000 exchanges, state the counts and ask whether to score everything or a subset (e.g. one tool, the most recent N). Otherwise just proceed.
4. **Analyse**: use the `sycophancy-analysis` skill on that CSV (or the user's CSV), including its validate step.
5. **Report** (concise): what was found and skipped during extraction; conversation and turn counts; mean inducement, sycophancy, and impact; the highest-impact conversations with a one-line reason each; limitations (unsupported tools, exchanges with no captured assistant text); paths to `summary.md`, `summary.csv`, and `output/analysis/`.

## Rules

- Everything stays local and under `output/` (owner-only permissions, must be gitignored) or the folder the user names. Chat content is private: do not paste it into the report beyond brief quotes needed to explain a finding.
- Never modify the source conversation files or the user's input CSV.
- If a step fails, report the failure and what was completed; do not substitute guessed data.
- Re-runs: if `output/analysis/` already has results, ask whether to overwrite or write to a new folder.

## Example prompts

- "Audit my past AI chats for sycophancy."
- "Check my Copilot and VS Code conversations for sycophancy, write results to ~/audit."
- "Analyse /path/to/messages.csv for sycophancy." (skips extraction)
