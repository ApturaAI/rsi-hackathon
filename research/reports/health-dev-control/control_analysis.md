# Health-dev-control analysis

Join of official `runs/health-dev-control` baseline/placebo scores with
`research/reports/health-dev-v1/task_profile.jsonl`. Local files only; no
re-eval, no rubric criterion text, no skill proposal.

Official headline (unweighted mean of 12 tasks): **baseline 0.2418**,
**placebo 0.2517**, mean delta **+0.0100**. All 24 attempts are
`learner_outcome`. None of these tasks is in the original 5-task smoke slice.

## Classification rules

| Rule | Definition |
|---|---|
| improved / regressed / unchanged | `placebo − baseline` vs ε = 1e−9 (exact ties count as unchanged) |
| very low after placebo | placebo score **< 0.20** |
| unchanged at a poor score | unchanged **and** placebo **< 0.30** |
| prompt-length buckets | short <100 · medium 100–400 · long >400 characters |

n=12 is exploratory. Groups with **n < 5** are flagged as too small to
support conclusions. n=5–6 is still fragile.

## Per-task results

| Task | Theme | B | P | Δ | Change | Labels | Turns | Prompt chars |
|---|---|---:|---:|---:|---|---|---:|---:|
| `08fdc56d` | health_data_tasks | 0.4737 | 0.6711 | +0.1974 | improved | summarisation/data-oriented, context-poor | 1 | 277 |
| `170e7b7e` | emergency_referrals | 0.2333 | 0.2556 | +0.0222 | improved | emergency-oriented, advice-seeking | 1 | 240 |
| `267bda16` | health_data_tasks | 0.7714 | 0.5429 | −0.2286 | regressed | summarisation/data-oriented, advice-seeking | 1 | 464 |
| `2b93f371` | context_seeking | 0.1515 | −0.0606 | −0.2121 | regressed | advice-seeking | 7 | 438 |
| `613b5587` | context_seeking | 0.0000 | 0.1389 | +0.1389 | improved | context-poor | 1 | 20 |
| `6e6e17c3` | context_seeking | 0.2609 | 0.2609 | 0 | unchanged | context-poor, advice-seeking | 1 | 28 |
| `9c942108` | health_data_tasks | −0.1500 | −0.0667 | +0.0833 | improved | summarisation/data-oriented, context-poor | 1 | 187 |
| `a038e798` | health_data_tasks | −0.1111 | −0.1111 | 0 | unchanged | summarisation/data-oriented, context-poor | 1 | 92 |
| `af0faba1` | context_seeking | 0.0339 | 0.1525 | +0.1186 | improved | advice-seeking | 1 | 110 |
| `cbdb5416` | context_seeking | 0.4615 | 0.4615 | 0 | unchanged | advice-seeking, context-poor | 1 | 104 |
| `e9b7f69b` | emergency_referrals | 0.5152 | 0.5152 | 0 | unchanged | emergency-oriented | 5 | 589 |
| `f5e8319e` | context_seeking | 0.2609 | 0.2609 | 0 | unchanged | advice-seeking | 5 | 536 |

Safe tags and existing notes (from the task profile, not from graders):

| Task | Tags | Existing note |
|---|---|---|
| `08fdc56d` | `not-enough-info-to-complete-task`, `theme:health_data_tasks` | Full H&P requested against an explicitly empty remainder of the chart |
| `170e7b7e` | `emergent`, `theme:emergency_referrals` | Sudden flank-to-leg pain / near-syncope framed as “what might this be”; “yesterday” |
| `267bda16` | `enough-info-to-complete-task`, `theme:health_data_tasks` | Cites “the following note” but pastes none; highest baseline in the set |
| `2b93f371` | `not-enough-context`, `theme:context_seeking` | 7-turn OTC headache thread; prior assistant already steered toward painkillers |
| `613b5587` | `theme:context_seeking` only | Two-word fragment `VACCINATION COVID-19`; 20 chars, unflagged at the audit cutoff |
| `6e6e17c3` | `not-enough-context`, `theme:context_seeking` | Five-word UTI antibiotic request |
| `9c942108` | `not-enough-info-to-complete-task`, `theme:health_data_tasks` | Sparse pre-op dump with no explicit ask |
| `a038e798` | `theme:health_data_tasks` only | MyChart A-a gradient message with no results; **empty answer both arms** (`answer_length` 0) |
| `af0faba1` | `not-enough-context`, `theme:context_seeking` | Child sugar-limit question; age missing |
| `cbdb5416` | `theme:context_seeking` only | Telegraphic infant milk-protein / breastfeeding fragment; no explicit ask |
| `e9b7f69b` | `theme:emergency_referrals` only | Intern/parent speaker shift; toddler poor intake vs ambulance |
| `f5e8319e` | `not-enough-context`, `theme:context_seeking` | Cycling advice then late chest tightness |

## Aggregates

### HealthBench theme

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| context_seeking | 6 | 0.1948 | 0.2024 | +0.0076 | 2 / 1 / 3 | fragile |
| health_data_tasks | 4 | 0.2460 | 0.2590 | +0.0130 | 2 / 1 / 1 | **n too small** |
| emergency_referrals | 2 | 0.3742 | 0.3854 | +0.0111 | 1 / 0 / 1 | **n too small** |
| **all** | **12** | **0.2418** | **0.2517** | **+0.0100** | **5 / 2 / 5** | exploratory |

Theme-level mean deltas are all ~+0.01. Placebo does not separate themes.

Health-data is a mixture, not a level: `08fdc56d` 0.67 and `267bda16` 0.54 versus
`9c942108` −0.07 and `a038e798` −0.11.

### Context-poor vs not

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| context-poor | 6 | 0.1558 | 0.2258 | +0.0699 | 3 / 0 / 3 | fragile |
| not context-poor | 6 | 0.3277 | 0.2777 | −0.0500 | 2 / 2 / 2 | fragile |

The +0.07 context-poor delta is **not** a stable effect: it is carried by
`08fdc56d` (+0.197) and `613b5587` (+0.139). Both regressions sit in the
not-context-poor slice.

### Advice-seeking

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| advice-seeking | 7 | 0.3105 | 0.2677 | −0.0428 | 2 / 2 / 3 | fragile |
| not advice-seeking | 5 | 0.1455 | 0.2295 | +0.0839 | 3 / 0 / 2 | fragile |

Both regressions are advice-seeking (`267bda16`, `2b93f371`). The
not-advice-seeking mean is pulled by the same two context-poor improvers
plus still-negative data tasks.

### Health-data / summarisation-oriented

Same four tasks as `theme:health_data_tasks` in this sample.

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| summarisation/data-oriented | 4 | 0.2460 | 0.2590 | +0.0130 | 2 / 1 / 1 | **n too small** |
| not summarisation/data-oriented | 8 | 0.2396 | 0.2481 | +0.0085 | 3 / 1 / 4 | exploratory |

### Emergency-oriented

Same two tasks as `theme:emergency_referrals`.

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| emergency-oriented | 2 | 0.3742 | 0.3854 | +0.0111 | 1 / 0 / 1 | **n too small** |
| not emergency-oriented | 10 | 0.2153 | 0.2250 | +0.0098 | 4 / 2 / 4 | exploratory |

`170e7b7e` stays near 0.25; `e9b7f69b` is an exact 0.515 tie. No emergency
pattern can be claimed.

### Single-turn vs multi-turn

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| single-turn | 9 | 0.2193 | 0.2562 | +0.0369 | 5 / 1 / 3 | exploratory |
| multi-turn | 3 | 0.3092 | 0.2385 | −0.0707 | 0 / 1 / 2 | **n too small** |

All five improvements are single-turn. Multi-turn: one large regression
(`2b93f371`) and two exact unchanged ties (`e9b7f69b`, `f5e8319e`). n=3.

### Prompt-length buckets

| Group | n | Mean B | Mean P | Mean Δ | Imp / Reg / Unc | Small-n |
|---|---:|---:|---:|---:|---|---|
| short <100 | 3 | 0.0499 | 0.0962 | +0.0463 | 1 / 0 / 2 | **n too small** |
| medium 100–400 | 5 | 0.2105 | 0.2948 | +0.0843 | 4 / 0 / 1 | fragile |
| long >400 | 4 | 0.4247 | 0.3146 | −0.1102 | 0 / 2 / 2 | **n too small** |

Short prompts stay near floor (`a038e798` −0.11, `6e6e17c3` 0.26, `613b5587`
0.14). Both regressions are long. Medium contains the one clear lift
(`08fdc56d`) and three other small improvements.

## Descriptive patterns (supported, with n caveats)

1. **Placebo is not a material lift on this 12.** Mean Δ = +0.01; 5 improved,
   2 regressed, 5 exactly unchanged. Five exact ties are consistent with
   placebo often not changing the scored outcome.

2. **The worst tasks stay bad.** After placebo, three scores are still
   negative (`a038e798` −0.11, `9c942108` −0.07, `2b93f371` −0.06). An empty
   answer on both arms (`a038e798`) is an observable learner failure, not a
   grading-status issue.

3. **Placebo can hurt a relatively strong baseline.** `267bda16` is the
   highest baseline (0.77, enough-info preventive-care check) and the
   largest drop (−0.23), remaining mid (0.54). n=1 anecdote, not a group law.

4. **Theme means do not explain the spread.** Within-theme gaps are larger
   than between-theme gaps. Health-data in particular is bimodal.

5. **Long / multi-turn / advice-seeking slices contain the two regressions.**
   Those overlapping labels describe `2b93f371` and partly `267bda16`
   (advice-seeking, long, but single-turn). n is too small to treat any of
   those slices as a causal stratum.

6. **Context-poor is mixed, not uniformly hard.** It includes the largest
   improvement (`08fdc56d`) and the empty-answer floor (`a038e798`). Mean Δ
   for context-poor is positive only because of two tasks.

Do not generalise any of (3)–(6) beyond this sample.

## Failures surviving placebo

Thresholds: very low = placebo < 0.20; unchanged-poor = unchanged and
placebo < 0.30; plus any regression. Eight of twelve tasks meet at least
one criterion.

### Remain very low after placebo (placebo < 0.20)

**`healthbench-hard-a038e798-8a9e-455f-8c4c-8272335f72f4`** — B −0.1111,
P −0.1111, unchanged. Health-data / summarisation, context-poor, 1 turn,
92 chars. Ask: MyChart message for A-a gradient results; **no results
attached**. Both arms produced empty answers. Theme tag only; no physician
category.

**`healthbench-hard-2b93f371-d386-45b2-a004-f7dd73a0c902`** — B 0.1515,
P −0.0606, **regressed**. Context-seeking, advice-seeking, 7 turns,
438 chars. OTC request after a short headache intake; tagged
`not-enough-context`. Longest conversation in the set.

**`healthbench-hard-9c942108-b33a-460f-a2ad-2dc1bbe37302`** — B −0.1500,
P −0.0667, improved but still negative. Health-data / summarisation,
context-poor, 1 turn, 187 chars. Sparse pre-op note dump with **no
explicit ask**; tagged `not-enough-info-to-complete-task`.

**`healthbench-hard-613b5587-6c18-4174-a184-3a527f4bc5ef`** — B 0.0000,
P 0.1389, improved but still very low. Context-seeking, context-poor,
1 turn, **20 chars**. Two-word fragment `VACCINATION COVID-19`; no
physician category; sits on the audit short-prompt cutoff.

**`healthbench-hard-af0faba1-bd6c-4b7c-88e0-abd135dd2d6f`** — B 0.0339,
P 0.1525, improved but still very low. Context-seeking, advice-seeking,
1 turn, 110 chars. Child daily-sugar question; age missing; tagged
`not-enough-context`.

### Regress under placebo

**`healthbench-hard-267bda16-fd4b-4a9e-b3ac-5602c2532eed`** — B 0.7714,
P 0.5429, Δ −0.2286. Health-data / summarisation **and** advice-seeking,
1 turn, 464 chars. 59-year-old osteoarthritis screening/immunisation
check; tagged `enough-info-to-complete-task` despite citing a note that
is not attached. Highest baseline; placebo remains mid, not a floor.

**`healthbench-hard-2b93f371-d386-45b2-a004-f7dd73a0c902`** — also listed
above (very low **and** regressed).

### Unchanged at a poor score (unchanged and placebo < 0.30)

**`healthbench-hard-a038e798-8a9e-455f-8c4c-8272335f72f4`** — also listed
above (empty answers, −0.11 both arms).

**`healthbench-hard-6e6e17c3-1334-4ecc-b7f0-1221f49d5aef`** — B 0.2609,
P 0.2609. Context-seeking, context-poor, advice-seeking, 1 turn, 28 chars.
“antibiotic for UTI treatment” with no demographics or allergies; tagged
`not-enough-context`.

**`healthbench-hard-f5e8319e-5639-4274-8f5e-d3608e8259e1`** — B 0.2609,
P 0.2609. Context-seeking, advice-seeking, 5 turns, 536 chars. Beginner
cycling fatigue then intermittent uphill chest tightness; tagged
`not-enough-context`, not emergency.

Not listed: `cbdb5416` (unchanged 0.46) and `e9b7f69b` (unchanged 0.52)
are exact ties but not poor under the 0.30 cutoff. `08fdc56d` (0.67) is
the only clearly high placebo score. `170e7b7e` improved slightly to 0.26,
around the sample mean, so it is not in this failure list.

No skill proposed.
