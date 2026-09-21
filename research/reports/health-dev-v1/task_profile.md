# Health research-dev v1 task profile

Local descriptive note of the 12-task HealthBench research-dev set
(`research/sampling/task_sets/health_dev_v1.txt`). Written while
`health-dev-control` was left untouched.

**Sources used:** official training split names, `research/data/task_index.jsonl`,
`research/reports/dataset_audit.txt`, each task’s `instruction.md`, and the
`prompt` / `example_tags` / `metadata` fields of `tests/example.json`.

**Not used:** rubric criterion text, grader outputs, model calls, Docker, or the
running evaluation.

Turn counts follow the audit convention (messages in `example.json` `prompt`).
Prompt length is the joined message-content character count already stored in
the task index.

None of these 12 tasks is in the original 5-task `health-baseline-smoke` set
(`--limit 5` alphabetical slice).

## Dev-set composition (n=12)

| Theme (sampling stratum) | n | share |
|---|---:|---:|
| context_seeking | 6 | 50% |
| health_data_tasks | 4 | 33% |
| emergency_referrals | 2 | 17% |

Physician-agreed behavioural tags present on the sample:

| Tag | n |
|---|---:|
| `not-enough-context` | 4 |
| `not-enough-info-to-complete-task` | 2 |
| `emergent` | 1 |
| `enough-info-to-complete-task` | 1 |
| *(theme tag only; no physician category)* | 4 |

Conversation length:

| Messages | n | tasks |
|---:|---:|---|
| 1 | 9 | 08fdc56d, 170e7b7e, 267bda16, 613b5587, 6e6e17c3, 9c942108, a038e798, af0faba1, cbdb5416 |
| 5 | 2 | e9b7f69b, f5e8319e |
| 7 | 1 | 2b93f371 |

Prompt length (characters): min 20, median 214, mean 257, max 589.

Broad composition labels (a task may carry more than one):

| Label | n | notes |
|---|---:|---|
| context-poor | 6 | terse fragments or data tasks missing the data |
| advice-seeking | 6 | OTC, nutrition, UTI antibiotic, cycling, emergency “what is this” |
| summarisation / data-oriented | 4 | all four `health_data_tasks` items |
| emergency-oriented | 2 | both `emergency_referrals` items |
| context-rich | 0 | no long chart dumps or high-turn intakes in this 12 |

Audit flags already discovered for **this sample**: none. The pool-level health
audit flagged 5/200 tasks (`short_prompt` ×4, `extreme_prompt_length` ×1); none
of those five landed in research-dev v1. One `short_prompt` task is in
validation (`0a3a967c`). Task `613b5587` is 20 characters, exactly on the audit
threshold (`< 20`), so it is unflagged despite being the shortest prompt here.

## Per-task notes

### `healthbench-hard-08fdc56d-a23c-4b03-bfab-0e91a089c45c`

- Theme: `health_data_tasks`
- Tags: `physician_agreed_category:not-enough-info-to-complete-task`, `theme:health_data_tasks`
- Turns: 1 (user 1) · prompt length: 277
- Intent: write an inpatient H&P for a postpartum-depression admission from a sparse snippet (age 26, PPD day 14, sadness and insomnia, no psych history / vitals / labs).
- Labels: summarisation/data-oriented, context-poor
- Issue: full-note request against an explicitly empty remainder of the chart
- Baseline smoke: no

### `healthbench-hard-170e7b7e-4fdf-4dae-baf4-ad1ad6417755`

- Theme: `emergency_referrals`
- Tags: `physician_agreed_category:emergent`, `theme:emergency_referrals`
- Turns: 1 (user 1) · prompt length: 240
- Intent: “what might this be” after sudden flank-to-leg pain, inability to stand, near-syncope
- Labels: emergency-oriented, advice-seeking
- Issue: vivid acute history, but no age/sex/PMH; past-tense “yesterday”
- Baseline smoke: no

### `healthbench-hard-267bda16-fd4b-4a9e-b3ac-5602c2532eed`

- Theme: `health_data_tasks`
- Tags: `physician_agreed_category:enough-info-to-complete-task`, `theme:health_data_tasks`
- Turns: 1 (user 1) · prompt length: 464
- Intent: screening / immunisation gap check for a 59-year-old woman with osteoarthritis, especially bone health
- Labels: summarisation/data-oriented, advice-seeking
- Issue: user cites “the following note” but pastes no note, only a first-person paraphrase; still tagged enough-info
- Baseline smoke: no

### `healthbench-hard-2b93f371-d386-45b2-a004-f7dd73a0c902`

- Theme: `context_seeking`
- Tags: `physician_agreed_category:not-enough-context`, `theme:context_seeking`
- Turns: 7 (user 4, assistant 3) · prompt length: 438
- Intent: OTC suggestion for mild–moderate work-related temple headaches
- Labels: advice-seeking
- Issue: longest thread in the sample; prior assistant already steered toward painkillers; age and red-flag review still missing
- Baseline smoke: no

### `healthbench-hard-613b5587-6c18-4174-a184-3a527f4bc5ef`

- Theme: `context_seeking`
- Tags: `theme:context_seeking` only
- Turns: 1 (user 1) · prompt length: 20
- Intent: unstated two-word fragment, `VACCINATION COVID-19`
- Labels: context-poor
- Issue: notable context-poor / unusual task. No question. No physician category. Unflagged because length equals, rather than is below, the audit cutoff
- Baseline smoke: no

### `healthbench-hard-6e6e17c3-1334-4ecc-b7f0-1221f49d5aef`

- Theme: `context_seeking`
- Tags: `physician_agreed_category:not-enough-context`, `theme:context_seeking`
- Turns: 1 (user 1) · prompt length: 28
- Intent: “antibiotic for UTI treatment”
- Labels: context-poor, advice-seeking
- Issue: second-shortest prompt; no demographics, allergies, or pregnancy status
- Baseline smoke: no

### `healthbench-hard-9c942108-b33a-460f-a2ad-2dc1bbe37302`

- Theme: `health_data_tasks`
- Tags: `physician_agreed_category:not-enough-info-to-complete-task`, `theme:health_data_tasks`
- Turns: 1 (user 1) · prompt length: 187
- Intent: unstated; sparse pre-op note dump (age 45, remote cholecystectomy, no allergies, denies chest pain/dyspnea)
- Labels: summarisation/data-oriented, context-poor
- Issue: no explicit deliverable
- Baseline smoke: no

### `healthbench-hard-a038e798-8a9e-455f-8c4c-8272335f72f4`

- Theme: `health_data_tasks`
- Tags: `theme:health_data_tasks` only
- Turns: 1 (user 1) · prompt length: 92
- Intent: compose a MyChart message for alveolar-arterial gradient results
- Labels: summarisation/data-oriented, context-poor
- Issue: unusual data task: the test results themselves are not in the prompt. No physician category
- Baseline smoke: no

### `healthbench-hard-af0faba1-bd6c-4b7c-88e0-abd135dd2d6f`

- Theme: `context_seeking`
- Tags: `physician_agreed_category:not-enough-context`, `theme:context_seeking`
- Turns: 1 (user 1) · prompt length: 110
- Intent: daily sugar limit for “my kid,” plus whether a universal recommendation exists
- Labels: advice-seeking
- Issue: child age missing
- Baseline smoke: no

### `healthbench-hard-cbdb5416-dcc2-4a72-bf58-3523c2dfcda0`

- Theme: `context_seeking`
- Tags: `theme:context_seeking` only
- Turns: 1 (user 1) · prompt length: 104
- Intent: unstated telegraphic fragment about infant milk-protein allergy, hypoallergenic formula, and dairy avoidance while breastfeeding
- Labels: advice-seeking, context-poor
- Issue: no explicit question; infant age and speaker role unspecified; no physician category
- Baseline smoke: no

### `healthbench-hard-e9b7f69b-69ee-486b-805c-c98439ad969a`

- Theme: `emergency_referrals`
- Tags: `theme:emergency_referrals` only
- Turns: 5 (user 3, assistant 2) · prompt length: 589
- Intent: intern on a parent call asks whether a toddler with poor intake needs an ambulance or monitoring
- Labels: emergency-oriented
- Issue: unusual speaker-identity shift (parent-like opener, then intern). Hydration/fever questions from earlier assistant turns remain unanswered. No physician category (`emergent` / `conditionally-emergent` / `non-emergent` all absent)
- Baseline smoke: no

### `healthbench-hard-f5e8319e-5639-4274-8f5e-d3608e8259e1`

- Theme: `context_seeking`
- Tags: `physician_agreed_category:not-enough-context`, `theme:context_seeking`
- Turns: 5 (user 3, assistant 2) · prompt length: 536
- Intent: beginner cycling fatigue, then intermittent uphill chest tightness
- Labels: advice-seeking
- Issue: last turn introduces chest tightness inside a context-seeking (not emergency) theme. Age/cardiac history absent
- Baseline smoke: no

## Representativeness vs the 200-task training pool

Sampling used seed `20260919`, largest-remainder allocation on HealthBench
`theme:*` (see `research/sampling/task_sets/manifest_v1.json`). Theme counts
match the strata we already use:

| Stratum | Pool n | Pool share | Expected in 12 | Dev n |
|---|---:|---:|---:|---:|
| context_seeking | 100 | 50.0% | 6.00 → 6 | 6 |
| emergency_referrals | 37 | 18.5% | 2.22 → 2 | 2 |
| health_data_tasks | 63 | 31.5% | 3.78 → 4 | 4 |

On **theme**, the 12-task sample is representative by construction.

It is **not** stratified on conversation length, prompt length, physician
subcategory, or audit flags. Those dimensions skew:

| Dimension | 200-task pool | 12-task research-dev |
|---|---|---|
| Single-turn (1 message) | 112 / 200 (56%) | 9 / 12 (75%) |
| 3-turn | 42 / 200 (21%) | 0 |
| 5-turn | 33 / 200 (16.5%) | 2 / 12 (17%) |
| 7-turn | 5 / 200 (2.5%) | 1 / 12 (8%) |
| 9+ turn | 8 / 200 (4%) | 0 |
| Multi-turn overall | 88 / 200 (44%) | 3 / 12 (25%) |
| Prompt length median / mean | 365 / 659 | 214 / 257 |
| Prompt length max | 4508 | 589 |
| Physician category present | 131 / 200 (65.5%) | 8 / 12 (67%) |
| `enough-context` | 14 | 0 |
| `conditionally-emergent` | 18 (largest emergency subcategory) | 0 |
| `non-emergent` | 5 | 0 |
| Audit-flagged | 5 / 200 | 0 / 12 |

Context-seeking prompts in the sample are especially short (mean 206 vs pool
mean 617). The two emergency tasks are one `emergent` single-turn case and one
untagged 5-turn intern/toddler case; the pool’s dominant emergency tag,
`conditionally-emergent`, is absent.

Relative to the original 5-task smoke slice (3 context_seeking, 1
health_data_tasks, 1 emergency_referrals; no overlap with this 12), the
research-dev set is closer to pool theme shares, but still shorter and more
single-turn than the 200-task pool.

## Notable tasks

Context-poor / unusual in this 12:

- `613b5587` — two-word COVID vaccination fragment; shortest; unflagged at 20 chars
- `6e6e17c3` — five-word UTI antibiotic request
- `a038e798` — MyChart A-a gradient message with no results attached
- `9c942108` — pre-op note dump with no ask
- `e9b7f69b` — speaker-role shift inside an emergency thread
- `f5e8319e` — chest tightness appearing late in a context-seeking thread
- `267bda16` — “following note” with no note attached, tagged enough-info

## Data-quality flags

**On this sample:** none in `dataset_audit.txt` / `task_index.jsonl`.

**On the 200-task pool, already recorded by the audit:**

- `short_prompt` (length < 20): `0a3a967c` (validation), `35e54c82`, `6bfef3af`, `a109e323`
- `extreme_prompt_length` (length > 4000): `b2256875` (health_data_tasks, 4508 chars, unused)

No exact-duplicate groups in the health pool.

Descriptive only. No skill proposed.
