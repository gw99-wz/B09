---
name: method-experiment-provenance
description: Write or repair an auditable Methods & Experiments section from raw configs, logs, code and dataset notes. Enforces a parameter ledger so every number traces to a material locator, blocks hand-typed numbers, and generates a reproduction checklist plus author queries. Use when the task asks for a methods/experimental-setup chapter, parameter alignment with config/log/code, reproducibility or limitation disclosure.
---

# Method & Experiment Provenance Kit

Turns scattered experiment records into a **Methods + Experimental Setup + Reproducibility + Limitations** draft where:

- every numeric value is rendered from a **parameter ledger** whose entries carry a `file:line` locator and a quote;
- a **numeric firewall** rejects any number that was not produced by a slot;
- conflicting materials are **never resolved by guessing** — they become author queries;
- a **reproduction checklist** is generated deterministically, with `[MISSING]` for absent facts.

The model writes prose around slots. It does not type measured values.

## When to use

Trigger on requests such as: "write the methods section", "align the numbers with the config", "make this reproducible", "extract the experimental setup", "check whether the hyperparameters match the logs", or any task that supplies configs/logs/code/dataset notes and asks for a methods-style section.

Do **not** use it to invent results, metrics or claims not present in the materials. The kit deliberately has no path for that.

## Inputs

| Input | Path | Notes |
|-|-|-|
| Case descriptor | `/input/case.json` | `output_contract` is parsed dynamically; never assume field names |
| Materials | any files next to the case / declared paths | yaml, json, toml, ini, log, sh, py, md, csv, tex |
| Draft (optional) | `work/draft.src.md` | written by the agent; slots only for numbers |

## Outputs (under `--out`)

| File | Purpose |
|-|-|
| `draft.md` | rendered, editable section (only emitted when the firewall passes) |
| `draft.rejected.md` | rendered but rejected; present only on hard failure |
| `param_table.md` | name / value / unit / scope / status / locator |
| `repro_checklist.md` | version, environment, data, seeds, commands, expected artifacts; `[MISSING]` marker |
| `author_queries.md` | every unresolved gap and the exact question for the author |
| `gaps.json` | machine-readable gap register |
| `ledger.json` | the single source of truth for values |
| `audit.json` | render errors, unbound numbers, limitation issues, substitutions |
| `result.json` | `case_id` + all `output_contract` fields + source map + uncertainty |
| `coverage.json` | six-class completeness matrix |
| `limitations.json` | limitation audit findings |
| `pack_report.json` | file-count / size / suffix self-check |

## Non-negotiable rules

1. **No hand-typed numbers in the draft.** Any measured value must be a slot:
   `{{P:<param_id or param_name>}}`, `{{D:<dataset_id>}}`, `{{C:<control_id>}}`.
   A literal number that is not a heading/list number, a cross-reference, or in
   `--allow` is rejected with `E_UNBOUND_NUMBER`.
2. **Unknown slots are hard errors** (`E_UNKNOWN_SLOT`), never silently rendered.
3. **Conflicts are not resolved.** If two materials disagree, the ledger marks
   `conflict`; a slot on that parameter fails with `E_CONFLICT_SLOT`; the pair
   goes to `author_queries.md`.
4. **Gaps are not dropped.** Missing coverage or reproducibility items become
   `[MISSING]` markers and author queries.
5. **The contract is dynamic.** `output_contract` shapes (list / dict / string)
   are all parsed; unmapped fields are written as `null` and listed in
   `unresolved_contract_fields`.

## Workflow

`$SKILL` below is the directory that contains this `SKILL.md`
(the evaluator installs it at `/skills/weekly-skill`; substitute accordingly).

### 1. Parse the case and build the ledger

```bash
python "$SKILL/scripts/run.py" init --case /input/case.json --work /app/work
```

This writes `work/pk/ledger.json`, `contract.json`, `materials.json`,
`datasets.json`, `controls.json`, and a skeleton `work/draft.src.md`.

Optional model-proposed parameters go in `work/param_proposals.json`:

```json
[{"key": "learning_rate", "value": "0.001",
  "locator": {"file": "config.yaml", "line": 3, "quote": "learning_rate: 0.001"}}]
```

They are accepted only if the quote really occurs at the locator and the value
matches the quote; otherwise `E_PROPOSAL_QUOTE_NOT_FOUND` / `E_PROPOSAL_VALUE_MISMATCH`.

### 2. Write the draft

Edit `work/draft.src.md`. Required sections: `Materials and Data`,
`Method Steps` (numbered, each with input / operation / output / decision),
`Experimental Setup` (hardware, software, train/val/test, parameters),
`Baselines and Controls`, `Reproducibility`, `Limitations`.

Use slots for every number. For an unknown fact write `{{?key}}`; it renders as
`[待确认:key]` and lands in the queries file.

### 3. Check, render, audit

```bash
python "$SKILL/scripts/run.py" check --case /input/case.json --work /app/work --out /app/output \
    --draft /app/work/draft.src.md [--allow /app/work/allowlist.txt]
```

Exit codes: `0` ok/partial, `2` hard failure, `1` usage/IO error.

### 4. Read the audit before shipping

- `E_UNBOUND_NUMBER` — replace the literal with a slot from `ledger.json`.
- `E_UNKNOWN_SLOT` — the id/name does not exist; inspect `ledger.json`.
- `E_CONFLICT_SLOT` — resolve with the author; do not pick a value.
- `E_VAGUE_LIMIT` — rewrite the limitation as a concrete failure scenario.
- `E_MISSING_LIMITS` — add the Limitations section.

### 5. Hand off

Ship `draft.md` only when exit code is `0`; always ship `author_queries.md`,
`repro_checklist.md` and `result.json`, including honest `partial` status.

## Slot grammar

| Slot | Renders |
|-|-|
| `{{P:train_batch_size}}` | `raw` value + unit |
| `{{P:P_train_batch_size}}` | same, by ledger id |
| `{{P:x.raw}}` / `{{P:x.unit}}` / `{{P:x.name}}` | field access |
| `{{D:D1}}` | dataset name + version |
| `{{C:C1}}` | baseline name + version |
| `{{?commit}}` | `[待确认:commit]` + query |

## Failure codes

| Code | Meaning | Fix |
|-|-|-|
| `E_UNBOUND_NUMBER` | literal number outside a slot | use `{{P:...}}` or add to allowlist with a reason |
| `E_UNKNOWN_SLOT` | slot id/name not in ledger | correct the name or add a proposal |
| `E_CONFLICT_SLOT` | ledger value is ambiguous | author confirmation; never choose |
| `E_LEDGER_MISMATCH` | quote not found at locator | re-extract; candidate dropped |
| `E_PROPOSAL_*` | model-proposed value failed verification | fix quote or drop the claim |
| `E_VAGUE_LIMIT` | banned boilerplate in Limitations | rewrite with scenario/scope |
| `E_SHALLOW_LIMIT` / `E_NO_SCENARIO` | limitation lacks a concrete failure case | add scenario + boundary |

## What this Skill does not do

- It does not invent values, metrics or citations. Missing facts stay missing.
- It does not guarantee that the materials are correct — only that the draft is
  faithful to them.
- PDF-only materials without a text layer need OCR first; the kit then treats the
  OCR text as a material with the same locator discipline.
- It does not render PDF/TeX. The draft is Markdown/LaTeX-ready text.

## Minimal example

`examples/mini/` contains a synthetic case (config + log + dataset note +
script), a slot draft, and a generated `out/` marked as an example. Run:

```bash
python "$SKILL/src/reproduce.py"
```

See `docs/METHOD.md` for thresholds, `docs/USAGE.md` for a full walkthrough,
`docs/LIMITS.md` for scope and failure modes.
