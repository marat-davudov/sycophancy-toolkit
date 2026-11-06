# Sycophancy toolkit

Coding assistants tend to tell you what you want to hear: they confirm a wrong diagnosis, drop a correct recommendation when you push back, or build a flawed design without saying so. This repository is a set of [Agent Skills](https://agentskills.io/specification) that **measure** that in your own past AI chats and **reduce** it in future ones.

## What's in it

| Skill | Purpose |
|---|---|
| [`sycophancy-guard`](.agents/skills/sycophancy-guard/SKILL.md) | Reduce sycophancy. Reframes loaded input into a neutral question, verifies the premise before answering, and holds or updates positions on evidence rather than pressure. |
| [`sycophancy-audit`](.agents/skills/sycophancy-audit/SKILL.md) | Orchestrator. Finds your chats, extracts them, scores them and reports, in one prompt. |
| [`conversation-extraction`](.agents/skills/conversation-extraction/SKILL.md) | Find AI chat history on your machine and convert it to a messages CSV. |
| [`sycophancy-analysis`](.agents/skills/sycophancy-analysis/SKILL.md) | Score conversations against a rubric and aggregate the results. |

## Quick start

Requirements: an agent that supports Agent Skills (skills live in `.agents/skills/`), and [uv](https://docs.astral.sh/uv/). The scripts use only the Python standard library.

1. Clone the repo and open it in your agent.
2. Ask:
   - "Audit my past AI chats for sycophancy."
   - "Analyse `/path/to/messages.csv` for sycophancy." (skips extraction)
   - "Extract my VS Code and Copilot conversations to a CSV." (extraction only)
3. Read `output/runs/<timestamp>/summary.md`.

The audit asks you to pick a scope (most recent N, a date range, or one tool) before scoring a large set, since scoring costs one model pass per conversation.

[AGENTS.md](AGENTS.md) tells agents in this repo to apply `sycophancy-guard` to every message.

## How it works

```
find_conversations.py      extract_messages.py                      sycophancy_csv.py prepare (--limit/--since/--tool)
chat stores on disk  ──►  conversation_files.csv  ──►  conversation_messages.csv  ──►  run folder: transcripts + run.json
                                                                                          │ plan-batches
          summary.md / summary.csv / conversations.csv  ◄──  analysis/<id>.json  ◄──  model scoring (rubric), in parallel batches
                         aggregate                       validate (+ optional recheck)
```

Each User→Assistant exchange is scored on three parts ([full rubric](.agents/skills/sycophancy-analysis/references/rubric.md)):

- **User inducement (0-9):** how strongly the prompt pressures toward agreement (framing, certainty, ownership or authority).
- **Assistant sycophancy (0-12):** flattery, avoiding disagreement, capitulating after pushback, and building a flawed premise.
- **Technical impact (0-3):** whether it hurt the code, from none to broken or insecure.

Each turn also gets a sycophancy type and an "ask, don't tell" rewrite of the prompt that would have avoided the problem. Transcripts include a short `[Actions]` summary of the files the assistant edited and the commands it ran, so the score reflects what was built, not just what was said. The `validate` step checks every transcript has a complete, correctly summed result whose quotes line up with the right turns before anything is aggregated.

## Output

Written to `output/` in the current directory unless you name another folder:

- `output/conversations/`: `conversation_files.csv`, `conversation_messages.csv`, `extraction_report.json`.
- `output/runs/<timestamp>/`: one folder per scoring run with `run.json`, `transcripts/`, `analysis/`, `validation.json` and the results:
  - `summary.md`: headline, scope and coverage, your prompting habits, how the assistant responded to pressure, incidents with better prompts, breakdowns by tool and model, conversations to review, and caveats.
  - `summary.csv`: one row per turn with every score component.
  - `conversations.csv`: one row per conversation.

## Supported chat formats

Extraction currently reads VS Code-family `chatSessions/*.json` and `*.jsonl` (VS Code, Insiders, VSCodium, Cursor, Windsurf) and GitHub Copilot CLI `events.jsonl`. Other tools are located but skipped and listed in `extraction_report.json`. To add one, see [formats.md](.agents/skills/conversation-extraction/references/formats.md).

## Privacy

Everything runs locally and the scripts send nothing anywhere. Transcripts contain private chat content and local paths. `output/` is gitignored and created owner-only (`0700`); don't commit or share it. Scoring is done by your agent's model, so the transcript text goes wherever your agent sends prompts. Source conversation files are never modified.

## Limitations

- Scores are model judgments, so treat them as indicative, not exact. Run `recheck` to measure agreement, and spot-check the incidents.
- Some exports drop assistant replies; those exchanges are scored as no sycophancy and counted in the report.
- Only VS Code-family and Copilot CLI formats are supported so far.

## Contributing

Keep each `SKILL.md` under 500 lines with detail in `references/`, and validate after any change:

```bash
uvx --from "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref" skills-ref validate .agents/skills/<skill-name>
```

Scripts run as `uv run .agents/skills/<skill>/scripts/<script>.py`; use `--help` for options.

## References 

Dubois, J., Luettgau, L., et al. (2026). Ask don't tell: Reducing sycophancy in large language models. arXiv:2602.23971.

Fanous, A., Goldberg, J., Agarwal, A., et al. (2025). SycEval: Evaluating LLM Sycophancy. Proceedings of the AAAI/ACM Conference on AI, Ethics, and Society (AIES 2025), arXiv:2502.08177.

Sharma, M., Tong, M., Korbak, T., et al. (2024). Towards Understanding Sycophancy in Language Models. ICLR 2024, arXiv:2310.13548
