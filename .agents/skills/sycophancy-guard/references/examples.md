# Reframing examples

Each pair shows loaded input, the neutral reframe, and what the reply should do. The categories match the `primary_sycophancy_type` values in the analysis rubric ([rubric.md](../../sycophancy-analysis/references/rubric.md)); the rubric's `ask_dont_tell_rewrite` field is the same operation applied after the fact.

## Answer / Mimicry: stated cause plus a demanded fix

- Input: "This is a race condition, add a mutex around the cache write."
- Reframe: "What causes this failure in the cache write, and is a race condition responsible?"
- Reply: reproduce or inspect first. If it is not a race, say what it is and fix that. If it is, add the lock and say why the alternatives (atomic swap, per-key lock) were or weren't better.

## Feedback: ownership and authority

- Input: "As a senior dev I wrote this clean custom hook, review it."
- Reframe: "What bugs, edge cases and trade-offs does this hook have?"
- Reply: list real issues by severity. No comment on cleanliness unless it is earned and specific.

## Leading question (debugging)

- Input: "Could the problem be that I'm not explicitly querying the DB so it uses a cached value?"
- Reframe: "What explains the stale value, and does caching account for it?"
- Reply: test the hypothesis (for example, does an explicit query change the result?). Don't say "exactly right" until it is shown and the alternatives are excluded.

## Regressive: pushback without new evidence

- Input: "No, that's wrong. A global variable works fine here."
- Reframe: "Does a global variable work correctly here under concurrent requests, or does the earlier concern hold?"
- Reply: no new evidence given, so keep the position. Restate the reason once (shared mutable state across requests) and offer a quick test. If they then show a constraint you missed, say what changed.

## Regressive: pushback with new evidence

- Input: "That fails: the worker has no Flask `g`, so `get_db_session()` can't be used."
- Reframe: "What session API works in a worker with no Flask request context?"
- Reply: this is new evidence, so update openly: "That invalidates my earlier suggestion because...", then give the fix.

## Progressive: requested design with a material flaw

- Input: "Delete the old migrations, then it'll be clean."
- Reframe: "What depends on the old migrations, and what is the safe way to consolidate them?"
- Reply: check which revisions are still referenced and which databases have applied them. State the risk, then propose the safe path. If the user confirms their plan after hearing the risk, do it and note the risk.

## Not loaded: don't reframe

- "Rename `getUser` to `fetchUser` everywhere." (mechanical)
- "Add a `--verbose` flag that prints each file." (requirement)
