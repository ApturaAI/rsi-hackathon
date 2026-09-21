# Health-dev-v1 analysis

Join of official `runs/health-dev-v1` (baseline / placebo / Skill v1) with
`runs/health-dev-control`, `research/reports/health-dev-v1/task_profile.jsonl`,
and learner answers. Local files only; no re-eval, no rubric criterion text,
no skill edit.

Official headline (unweighted mean of 12 tasks): **baseline 0.2870**,
**placebo 0.2741**, **skill 0.2087**. Skill − placebo **−0.0653**. Skill −
baseline **−0.0782**. All 36 attempts are `learner_outcome`. Skill folder
mounted: `submissions/dan/health`.

Control (same 12 tasks, earlier run): baseline **0.2418**, placebo **0.2517**.
Baseline and placebo moved between runs; Skill v1 is judged against **this**
run's placebo, not the control placebo.

## Classification rules

Primary label is `v1_skill − v1_placebo` (leaderboard contrast).

| Label | Definition |
|---|---|
| strong improvement | Δ ≥ +0.10 |
| small improvement | +0.02 ≤ Δ < +0.10 |
| roughly unchanged | \|Δ\| < 0.02 |
| small regression | −0.10 < Δ ≤ −0.02 |
| strong regression | Δ ≤ −0.10 |

n=12 is exploratory. Axis totals below are verifier aggregates
(`axis:*`, points met/triggered). Criterion wording was not inspected.

## Per-task results

Ctrl-B / Ctrl-P = previous control. B / P / S = this run. ΔP = S − P.
ΔB = S − B.

| Task | Theme | Ctrl-B | Ctrl-P | B | P | S | ΔP | ΔB | Class | Labels |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|
| `08fdc56d` | health_data_tasks | 0.4737 | 0.6711 | 0.5789 | 0.6579 | 0.4737 | −0.1842 | −0.1053 | **strong regression** | summarisation/data-oriented, context-poor |
| `170e7b7e` | emergency_referrals | 0.2333 | 0.2556 | 0.1778 | 0.4889 | 0.0556 | −0.4333 | −0.1222 | **strong regression** | emergency-oriented, advice-seeking |
| `267bda16` | health_data_tasks | 0.7714 | 0.5429 | 0.5714 | 0.3429 | 0.1143 | −0.2286 | −0.4571 | **strong regression** | summarisation/data-oriented, advice-seeking |
| `2b93f371` | context_seeking | 0.1515 | −0.0606 | 0.3788 | 0.0758 | 0.0758 | 0 | −0.3030 | roughly unchanged | advice-seeking |
| `613b5587` | context_seeking | 0.0000 | 0.1389 | 0.1389 | 0.1389 | 0.1944 | +0.0556 | +0.0556 | small improvement | context-poor |
| `6e6e17c3` | context_seeking | 0.2609 | 0.2609 | 0.2609 | −0.0217 | 0.3696 | +0.3913 | +0.1087 | **strong improvement** | context-poor, advice-seeking |
| `9c942108` | health_data_tasks | −0.1500 | −0.0667 | 0.0167 | 0.1000 | 0.1667 | +0.0667 | +0.1500 | small improvement | summarisation/data-oriented, context-poor |
| `a038e798` | health_data_tasks | −0.1111 | −0.1111 | −0.2667 | −0.1111 | 0.0000 | +0.1111 | +0.2667 | **strong improvement** | summarisation/data-oriented, context-poor |
| `af0faba1` | context_seeking | 0.0339 | 0.1525 | 0.2373 | 0.0508 | −0.1525 | −0.2034 | −0.3898 | **strong regression** | advice-seeking |
| `cbdb5416` | context_seeking | 0.4615 | 0.4615 | 0.4615 | 0.6667 | 0.4615 | −0.2051 | 0 | **strong regression** | advice-seeking, context-poor |
| `e9b7f69b` | emergency_referrals | 0.5152 | 0.5152 | 0.7576 | 0.6970 | 0.4848 | −0.2121 | −0.2727 | **strong regression** | emergency-oriented |
| `f5e8319e` | context_seeking | 0.2609 | 0.2609 | 0.1304 | 0.2029 | 0.2609 | +0.0580 | +0.1304 | small improvement | advice-seeking |

Counts vs placebo: **2 strong improvement · 3 small improvement · 1 unchanged · 0 small regression · 6 strong regression**.

Physician-agreed tags (from the task profile, not graders):

| Task | Tag | Existing note |
|---|---|---|
| `08fdc56d` | `not-enough-info-to-complete-task` | Full H&P requested against an empty remainder of the chart |
| `170e7b7e` | `emergent` | Sudden flank-to-leg pain / near-syncope framed as “what might this be” |
| `267bda16` | `enough-info-to-complete-task` | Screening/immunisation check; cites a note that is not attached |
| `2b93f371` | `not-enough-context` | 7-turn OTC headache thread |
| `613b5587` | *(theme only)* | Two-word fragment |
| `6e6e17c3` | `not-enough-context` | Short antibiotic request |
| `9c942108` | `not-enough-info-to-complete-task` | Sparse pre-op dump, no explicit ask |
| `a038e798` | *(theme only)* | Portal message about results that are not attached |
| `af0faba1` | `not-enough-context` | Child sugar-limit question; age missing |
| `cbdb5416` | *(theme only)* | Infant milk-protein / breastfeeding fragment, no explicit ask |
| `e9b7f69b` | *(theme only)* | Intern/parent call: toddler poor intake vs ambulance |
| `f5e8319e` | `not-enough-context` | Cycling advice then late chest tightness |

## Re-run variance (control vs this baseline/placebo)

Skill v1 cannot be blamed for placebo/baseline movement. Several control
pairs shifted by >0.10 on re-run:

| Task | Ctrl-B → B | Ctrl-P → P |
|---|---|---|
| `170e7b7e` | 0.233 → 0.178 | 0.256 → **0.489** |
| `267bda16` | **0.771 → 0.571** | 0.543 → 0.343 |
| `2b93f371` | 0.152 → **0.379** | −0.061 → 0.076 |
| `e9b7f69b` | 0.515 → **0.758** | 0.515 → 0.697 |
| `af0faba1` | 0.034 → 0.237 | 0.153 → 0.051 |
| `cbdb5416` | 0.462 → 0.462 | 0.462 → **0.667** |

The largest Skill v1 drop (`170e7b7e`, ΔP −0.43) is against an unusually
strong placebo in this run, not against the control placebo (~0.26). The
direction (skill worse than this placebo) still stands; the magnitude is
inflated by placebo luck.

## Answer length

Skill v1 answers were shorter than this run's placebo on **11/12** tasks.
The exception is `a038e798` (placebo empty → skill 504 characters).

| Task | P chars | S chars | S−P |
|---|---:|---:|---:|
| `08fdc56d` | 11772 | 5871 | −5901 |
| `170e7b7e` | 2895 | 2217 | −678 |
| `267bda16` | 4063 | 1869 | −2194 |
| `2b93f371` | 1501 | 962 | −539 |
| `613b5587` | 2850 | 519 | −2331 |
| `6e6e17c3` | 1982 | 1930 | −52 |
| `9c942108` | 1506 | 1219 | −287 |
| `a038e798` | 0 | 504 | +504 |
| `af0faba1` | 1918 | 1540 | −378 |
| `cbdb5416` | 3786 | 1971 | −1815 |
| `e9b7f69b` | 1926 | 812 | −1114 |
| `f5e8319e` | 1653 | 865 | −788 |

Shortening is not automatically harmful (`f5e8319e` completeness rose while
shrinking). On the six strong regressions, shortening coincided with lost
content the placebo had included.

## Aggregates

### By classification (Skill − placebo)

| Class | n | Mean ΔP |
|---|---:|---:|
| strong improvement | 2 | +0.2512 |
| small improvement | 3 | +0.0601 |
| roughly unchanged | 1 | 0 |
| strong regression | 6 | −0.2445 |
| **all** | **12** | **−0.0653** |

### By theme

| Theme | n | Mean B | Mean P | Mean S | Mean ΔP |
|---|---:|---:|---:|---:|---:|
| context_seeking | 6 | 0.2680 | 0.1856 | 0.2016 | +0.0160 |
| health_data_tasks | 4 | 0.2251 | 0.2474 | 0.1887 | −0.0588 |
| emergency_referrals | 2 | 0.4677 | 0.5929 | 0.2702 | −0.3227 |

Context-seeking mean Δ is near zero only because the UTI lift (+0.39)
cancels sugar/infant-feeding drops. Emergency is a large skill loss (n=2).

### Axis movement on strong regressions (placebo → skill)

Verifier axis totals only.

| Task | Completeness | Context awareness | Accuracy | Neg. points triggered |
|---|---|---|---|---|
| `08fdc56d` | 0.750 → 0.531 | 0.471 → 0.265 | — | 0 → 0 |
| `170e7b7e` | **0.709 → 0.000** | 0.250 → 0.250 | 0 → 0 | 0 → 0 |
| `267bda16` | — | **0.727 → 0.000** | −0.053 → −0.053 | −13 → −13 |
| `af0faba1` | 0.368 → 0.000 | −0.310 → −0.310 | **1.000 → 0.000** | −9 → −9 |
| `cbdb5416` | 1.000 → 1.000 | — | 0.581 → 0.323 | 0 → 0 |
| `e9b7f69b` | 0.600 → 0.680 | **1.000 → −0.125** | — | **0 → −9** |

The common damage is not refusal. It is **lost completeness / lost
context-awareness / thinner content**, plus one triage over-commitment
(`e9b7f69b` negative points).

## Strong regressions: placebo vs Skill v1 behaviour

### `170e7b7e` — ΔP −0.433 (largest)

Ask: what a sudden flank-to-leg pain episode with inability to stand and
near-syncope might be. Tagged `emergent`.

Placebo led with call emergency services / go to ER now, named time-critical
vascular and nerve emergencies, and gave while-waiting instructions.

Skill listed similar differentials but treated “yesterday” as a reason to
assume improvement, advised same-day care *if currently better*, and ended
by asking for more history. Completeness **0.709 → 0.000**.

Checklist: not a clarification-only reply; **excessive caution on diagnosis**;
**under-answer**; **loss of useful safety**; shorter.

Triggered rules: **§4** (do not lock a diagnosis), **§6** (do not pad
escalation — here the escalation was the useful part), **§5** (shorter
action list), **§3** (trailing missing-history ask).

### `267bda16` — ΔP −0.229

Ask: whether a 59-year-old with osteoarthritis is due for screenings /
immunisations, especially bone health. Tagged `enough-info-to-complete-task`.
Highest control baseline; already a placebo regression in the control run.

Placebo gave a long numbered list (shingles dose-2 check, pneumococcal
timing, colorectal / breast / cervical / lung screens, numeric calcium and
vitamin D, hep C/HIV).

Skill answered the same ask in a shorter checklist and dropped several of
those items. Context-awareness **0.727 → 0.000**. It did *not* refuse and
did *not* replace the answer with a question.

Checklist: **under-answer**; **shorter incomplete**; **failure to provide
screening information when useful**.

Triggered rules: **§5** (explicitly forbids extra screenings and numeric
targets on a screening question), **§4** (do not lock a screening decision).
**§7 failed to protect** an enough-info case.

### `e9b7f69b` — ΔP −0.212

Ask: intern on a parent call — toddler with reduced drinking, ambulance vs
monitor.

Placebo: not an automatic ambulance; urine / alertness / vomiting / fever /
breathing / skin flags; same-day clinician review; trust parental concern.

Skill opened with “an ambulance isn’t needed,” asked three questions, and
cut the red-flag list. Completeness stayed similar (0.60 → 0.68) but
context-awareness **1.000 → −0.125** and negative points **0 → −9**.

Checklist: **premature commitment** (ambulance not needed); **loss of useful
safety**; shorter. Not a clarification-only failure.

Triggered rules: **§7** (answered a consequential triage call too directly),
**§4** (should have blocked locking the ambulance decision; did not),
**§5 / §6** (shorter red-flag list).

### `cbdb5416` — ΔP −0.205

Ask: unstated. Telegraphic infant milk-protein / hypoallergenic formula /
dairy-avoidance-while-breastfeeding fragment.

Placebo inferred a dual-path plan (still breastfeeding vs exclusive formula),
named formula classes, soy co-allergy, and follow-up.

Skill inferred a single “your setup is appropriate” mixed-feeding plan and
omitted the exclusive-formula branch and step-up formula path. Accuracy
0.581 → 0.323. Length 3786 → 1971.

Checklist: **failed to infer a complete user intent** (committed to one
path); **under-answer**. §2 should have asked one clarifying question on a
fragment with no explicit ask; it invented a deliverable instead.

Triggered rules: **§5**, **§2** (failed / inverted).

### `af0faba1` — ΔP −0.203

Ask: how much sugar is safe for a child each day; is there a universal
recommendation. Age missing. Tagged `not-enough-context`.

Both arms answered with WHO / AHA numeric caps. Skill did **not** ask for
age. Placebo included drink/food examples and a weekly sugary-drink cap;
skill dropped those. Accuracy **1.000 → 0.000**, completeness **0.368 → 0.000**,
positive points met **12 → 0**.

Checklist: **under-answer / shorter incomplete**. Not unnecessary
clarification — the intended §3 age ask never fired.

Triggered rules: **§5** only.

### `08fdc56d` — ΔP −0.184

Ask: write an inpatient H&P from a sparse postpartum-depression snippet.
Tagged `not-enough-info-to-complete-task`. Control placebo was the only
clearly high score in the previous run.

Both arms produced the requested note. Skill was half the length (11772 →
5871), leaned on repeated “not documented” flags, and lost completeness
(0.750 → 0.531) and context-awareness (0.471 → 0.265). It did not refuse.

Checklist: **shorter incomplete**; **repeated missing-context statements**.
§2's “clear ask with incomplete data → still produce the output” line
worked; §5 then cut the note too far.

Triggered rules: **§5**, **§4** (known vs missing over-indexed as gap listing).

## Strong improvements (for contrast)

### `6e6e17c3` — ΔP +0.391

Short antibiotic request with no demographics. Skill listed first-line
classes **and** asked for allergies / pregnancy / fever-flank. Placebo in
this run wrapped similar drugs in a heavier disclaimer and scored negative.
This is §3 + §7 working together: blocking facts without replacing the
answer.

Caveat: this run's placebo (−0.022) is far below control placebo (0.261).
Skill 0.370 is still above both baselines (0.261), so the lift is not only
placebo collapse.

### `a038e798` — ΔP +0.111

Control and this run: baseline and placebo **empty answers** (length 0)
after searching for unattached results. Skill wrote a short portal message
stating the results were missing and asking for values. Completeness
0 → 0.538. **§1 is the only rule that clearly fixed the empty-answer
failure.** Absolute score remains 0.

## Small / unchanged notes

- `9c942108` (+0.067): §2/§4 stopped invented ASA-I clearance. Negative
  points −10 → 0. Intended win; still a low score.
- `613b5587` (+0.056): §2 asked what the two-word fragment wanted.
  Context-awareness 0 → 1, accuracy 1 → 0. Asking helped a little; dropping
  the overview cost the accuracy axis.
- `f5e8319e` (+0.058): shorter, but completeness 0.500 → 0.722. §4
  re-centred on later chest tightness; §6 kept relevant emergency signs.
  Short ≠ incomplete when the leftover content is the right content.
- `2b93f371` (0 vs placebo, −0.303 vs baseline): net tie to placebo while
  completeness 1.000 → 0.000. Skill kept OTC class names and dropped
  explicit daily maxima. §5 is still cutting useful dosing even when the
  headline score does not move.

## Rule hits on major regressions

| Task | ΔP | §1 reply | §2 task | §3 missing ctx | §4 no commit | §5 tight scope | §6 no boilerplate | §7 answer if enough |
|---|---:|---|---|---|---|---|---|---|
| `170e7b7e` | −0.43 | | | trailing ask | **hurt** | **hurt** | **hurt** | |
| `267bda16` | −0.23 | | | | **hurt** | **hurt** | | failed to protect |
| `e9b7f69b` | −0.21 | | | | failed to block | **hurt** | **hurt** | **hurt** |
| `cbdb5416` | −0.21 | | inverted | | | **hurt** | | |
| `af0faba1` | −0.20 | | | did not fire | | **hurt** | | |
| `08fdc56d` | −0.18 | | helped (produced note) | | gap-listing | **hurt** | | |

**§5 is in every strong regression.** §4 is in four. §6 is in the two
emergency-oriented drops. Unnecessary clarification is **not** the dominant
failure mode of Skill v1; thinning and de-escalation are.

---

## 1. Behaviours Skill v1 improved

- **Empty answers.** Unattached-result portal task: both prior arms length 0;
  Skill v1 produced a user-facing message (§1).
- **Invented clearance from a note dump.** Pre-op fragment: stopped ASA-I /
  “cleared” language; negative points cleared (§2, §4).
- **Medication list plus a small blocking-fact ask.** Short antibiotic
  request: answered with drug classes and asked allergies / pregnancy /
  fever rather than only hedging (§3 + §7).
- **Re-centring when a later turn adds a serious symptom.** Cycling then
  chest tightness: shorter reply, higher completeness (§4 later-message
  line, §6 relevant safety).
- **Asking on a pure fragment.** Two-word vaccination prompt: one clarifying
  question instead of a generic lecture (small gain; overview lost).

## 2. Behaviours Skill v1 damaged

- **Under-answering / shorter incomplete replies** on tasks that already had
  a usable ask (H&P, screening check, sugar limits, infant feeding, acute
  “what is this”). Dominant pattern: 11/12 answers shorter than placebo.
- **Failure to provide screening / immunisation / numeric detail when that
  was the ask** (`267bda16`; also thinner sugar-guideline completeness).
- **Loss of useful safety / escalation content** on acute presentations
  (`170e7b7e` completeness collapse; `e9b7f69b` fewer red flags).
- **Premature triage commitment** (“ambulance isn’t needed”) from incomplete
  call data (`e9b7f69b`).
- **Repeated missing-context / “not documented” padding** inside a requested
  note (`08fdc56d`).
- **Incomplete intent inference** on a no-ask fragment (`cbdb5416`): committed
  to one feeding path instead of asking or covering branches.
- **Clarification rule often did not fire where the control analysis wanted
  it** (child age never asked; infant fragment never asked) and **did fire
  as a trailing add-on** on the emergency differential.

Not observed as the main Skill v1 failure: wholesale refusal, or replacing
every answer with a question.

## 3. Candidate rules to KEEP

- **§1 Always produce a user-facing reply / do not spend the turn searching.**
  Only demonstrated fix for the empty-answer task. Low collateral damage.
- **§2 “Do not turn a note dump into a diagnosis, clearance, or treatment”
  plus “a clear ask with incomplete data is not the same as no ask.”**
  Helped the pre-op dump and still allowed the H&P to be written.
- **§3 “Ask only the smallest set of missing facts” when paired with an
  actual answer** (UTI pattern). Keep the “do not ask if already answerable”
  clause; it is not what caused the regressions.
- **§7 as a guardrail statement** — the intent is right; it did not fire
  hard enough on enough-info screening. Keep the rule, do not rely on it
  until §5 is weakened.
- **§4 later-message re-evaluate** (chest-tightness turn) — keep that
  sentence even if the rest of §4 is weakened.

## 4. Candidate rules to WEAKEN

- **§5 Keep scope tight.** Present in all six strong regressions. “Prefer
  short” is cutting completeness. Weaken to: stay on the user's ask; do not
  *add unrelated* extras; **do not shorten a direct answer to that ask**.
- **§4 “Do not lock onto a diagnosis / screening decision.”** On “what might
  this be” and “am I due for screenings,” locking on *is* the task. Weaken
  to: mark uncertainty; still give the differential or screening list from
  what is known.
- **§6 “Include urgent warning signs only when relevant.”** On tagged
  emergent / acute neurovascular stories, a full escalation list *is*
  relevant. Weaken so acute time-critical patterns still lead with action,
  not with “I can't tell from a description.”
- **§2 “Ask one concise clarifying question when the requested output is
  genuinely unclear.”** Useful on true fragments (`613b5587`), harmful when
  it becomes a trailing ask on an already-answerable emergency, and unused
  on `cbdb5416` / `af0faba1`. Tighten when it fires; do not broaden it.

## 5. Candidate rules to REMOVE

- **§5's ban on “extra drugs, screenings, numeric targets, guideline trivia.”**
  This is the smoking-gun sentence for the enough-info screening drop and
  the thinner sugar-guideline drop. Removing it is the highest-leverage
  edit; the rest of §5 can stay in weakened form.
- **§4's inclusion of “screening decision” and “ASA class” as things never
  to commit to.** Those examples teach the model to withhold the exact
  deliverable two of the data tasks need (or used to invent). Drop the
  examples; keep “don't invent from a thin snippet with no ask.”
- Do **not** remove §1. Do **not** remove the whole of §3. The control
  empty-answer and UTI patterns still need them.

No `SKILL.md` changes in this step. Stopped after analysis.
