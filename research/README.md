# Research layer

Local evaluation / capability-engineering tools around the **frozen** learner.
This directory is not part of the official submission path.

The harness in `src/skilltrainbench/` remains authoritative for scoring.
These scripts only read completed runs and training-task metadata.

## Do not

- Edit `hackathon.toml` or `src/skilltrainbench/`
- Overwrite `dataset/hackathon/`
- Copy rubric criteria, HLE answers/rationales, QF reference outputs, or Tau3 expected actions into skills
- Run `stbench eval` from these scripts (they never call models or Docker)

## Layout

```text
research/
  lib.py                         shared helpers
  audit/audit_dataset.py         training-task inventory + quality flags
  parsing/parse_run.py           join a completed stbench run
  sampling/build_task_sets.py    deterministic research-dev / validation sets
  sampling/task_sets/            `*_dev_v1.txt` / `*_validation_v1.txt`
  data/task_index.jsonl          derived task metadata
  reports/                       parse + audit summaries
  experiments/                   manifests + append-only log
  schemas/experiment_schema.json
```

## Workflow

```text
audit_dataset.py  →  task_index.jsonl
        ↓
build_task_sets.py --write  →  research-dev / validation name lists
        ↓
(you approve) stbench eval --tasks … --out runs/<id>
        ↓
parse_run.py --run runs/<id>
        ↓
append an experiment manifest
```

Development sets may be inspected. Validation sets stay unread until a
candidate intervention is evaluated.

## Commands

All of these are local and free:

```bash
uv run python research/audit/audit_dataset.py --all-domains
uv run python research/sampling/build_task_sets.py --write
uv run python research/parsing/parse_run.py --run runs/health-baseline
```

Consume a task set:

```bash
uv run stbench eval --domain health --arms baseline \
  --tasks "$(paste -sd, research/sampling/task_sets/health_dev_v1.txt)" \
  --out runs/health-dev-baseline
```

Do not run that eval unless it is explicitly approved. `--limit N` is an
alphabetical slice, not a research split.

## Data policy

| Source | Use |
|---|---|
| `dataset/hackathon/<bench>/tasks/` | read-only raw training tasks |
| official `splits/*/dev_task_names` | only legal local pool |
| official `heldout_task_names` | unused (folders are not present) |
| Health `example.json` | tags, turn counts, prompt length; **no criterion text** |
| HLE `metadata.json` / `question.txt` | category, length, hash; **no answer/rationale** |
| QF `task.toml` | difficulty/category/tags; **no tests/reference_data** |
| Tau3 `tests/config.json` | domain, action *counts*; **no expected action payloads** |
| `runs/*/eval_result.json` + `attempts.jsonl` | official scores, copied not recomputed |

## Task splits

`v1` sets use seed **`20260919`**.

| Domain | Dev | Validation | Stratum field |
|---|---:|---:|---|
| health | 12 | 12 | HealthBench `theme:*` |
| qf | 8 | 8 | `task.toml` difficulty, collapsed to hard/medium/easy/unknown |
| tau3 | 8 | 8 | `banking_knowledge` (single stratum) |
| hle | 12 | 12 | HLE `category` |

QF `task.toml` difficulty disagrees with the official paper tiers on some
tasks; we record that as a limitation rather than inventing a second label.
The single QF `easy` task is in the pool but was not drawn into `v1` (largest
remainder preferred the larger hard/medium strata).

Tau3 tasks share one policy wrapper in `instruction.md`. Duplicate detection
hashes the per-task simulated-user instructions, not that wrapper.

## Experiment naming

`{domain}-{purpose}-{n}` — example: `health-baseline-smoke`.

Record each approved run as JSON matching
`research/schemas/experiment_schema.json` and append one line to
`research/experiments/experiment_log.jsonl`.

Experiment zero is `health-baseline-smoke` (`runs/health-baseline`, 5
alphabetical tasks, baseline arm only).
