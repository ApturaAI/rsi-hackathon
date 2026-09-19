# Skill-writing hackathon

You are the curator. Write a **skill** (a folder with a `SKILL.md` plus any
supporting files) that makes a fixed **learner** model better at a domain. The
learner never changes; only your skill does. Your skill is scored on held-out
tasks you never see, with the same learner and the same limits you use here.

```
you (+ any AI assistant) ──write──▶ skill folder ──mounted read-only──▶ learner (frozen)
        ▲                                                                  │
        └─────────────── scores + trajectories on training tasks ◀────────┘
```

The learner is pinned in [`hackathon.toml`](hackathon.toml): model, agent harness,
per-task turn limits and the graders / simulated users some domains use. `stbench eval` applies that
file exactly, and the organizers score submissions and the autonomous baseline
with the same file.

| domain | benchmark | what the learner does | score per task |
|---|---|---|---|
| `qf` | QuantitativeFinance-Bench | solves a quantitative-finance task in a sandbox | task tests pass / fail |
| `health` | HealthBench | answers a health conversation | rubric grade from a model grader, 0–1 |
| `tau3` | τ³-bench | serves a simulated customer through tool calls | task assertions pass / fail |
| `hle` | Humanity's Last Exam | answers an expert-level question | answer graded by a model, pass / fail |

## Setup

Requirements: Docker (running), [uv](https://docs.astral.sh/uv/), Python 3.12+, and a Runware API key.

**Apple Silicon Mac:** task containers are amd64. In Docker Desktop, enable
Settings → General → **"Use Rosetta for x86_64/amd64 emulation on Apple Silicon"**
and Apply & restart; the default emulation crashes while the learner agent installs.
`stbench eval` warns you if it is off.

```bash
git clone <this repo> && cd <repo>
uv sync
cp .env_example .env          # then put your RUNWARE_API_KEY in .env
uv run stbench data pull      # downloads the training tasks into dataset/hackathon/
uv run stbench tasks --domain health
```

## The loop

Evaluate a skill on a few training tasks, with and without the skill:

```bash
cp -r submissions/example-team submissions/my-team   # then edit submissions/my-team/health/SKILL.md
uv run stbench eval --domain health \
  --skill submissions/my-team/health \
  --limit 8 --out runs/health-v1
```

It prints the score per arm and the tokens spent, and writes `runs/health-v1/eval_result.json`
(summary and per-task scores) and `runs/health-v1/attempts.jsonl` (every attempt, with the
learner's answer and its Harbor trial folder).
To read what the learner actually did, step by step:

```bash
uv run harbor view runs/health-v1/harbor-jobs     # opens the Harbor trajectory viewer
```

Useful flags:

- `--arms baseline,skill` (default) · add `placebo` to compare against a generic, content-free skill, which is what the leaderboard subtracts
- `--tasks name1,name2` to rerun exactly the tasks you care about
- `--limit N` to cap cost while iterating
- `--concurrency N` to run fewer containers at once (`qf` and `tau3` tasks each ask for 4–8 GB of RAM; use 1 on a laptop)

Then change the skill and run again. You can drive this loop with any coding
agent (Claude Code, Codex, ...): point it at this repo and let it call `stbench eval`.

## Scoring

- Each submitted skill runs on **private held-out tasks** from the same domain in three arms: no skill, a placebo skill, and your skill.
- **Score = pass rate with your skill − pass rate with the placebo.** Extra context on its own does not score.
- The learner, its turn and token limits, and the grader are the ones in `hackathon.toml`.
- The live leaderboard and the final ranking use **different** held-out sets.
- Your local numbers are measured on training tasks, so treat them as a guide.

## Rules

- **Learn from the training tasks only.** Do not copy held-out content, grading rubrics or answers from the public source datasets into a skill.
- **Tools must be self-contained.** Scripts in a skill run inside the task container: no external API calls and no credentials.
- **Don't change the learner.** Edits to `hackathon.toml` or the harness have no effect on your score.
- Every submission is checked for leaked task content and answer keys. A flagged skill scores zero.

## Submitting

Put each skill in `submissions/<team-name>/<domain>/`, then run
`uv run stbench check-skill submissions/<team-name>/<domain>` before you submit.
See [`submissions/README.md`](submissions/README.md).

## Cost tips

Every `stbench eval` spends your Runware credits. The learner runs once per task
per arm, and `health`, `tau3` and `hle` tasks also call a grader or simulated user. Start with `--limit 5`, add
tasks as the skill stabilises, and check the token and cost lines each run prints.
`qf` and `tau3` tasks run a full sandbox each and can take tens of minutes.

## What's in the repo

- `hackathon.toml` — the pinned learner contract
- `src/skilltrainbench/` — the harness: metering gateway, Harbor runtime, paired evaluator
- `submissions/` — your skills
