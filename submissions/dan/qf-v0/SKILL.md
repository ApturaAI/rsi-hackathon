---
name: quantitative-finance
description: >-
  Procedural policy for quantitative-finance sandbox tasks that read input data
  and write graded output files. Locate the real data, extract the exact spec,
  compute in a script rather than mentally, keep units and conventions explicit,
  then verify the written artifacts before finishing. Use when the task involves
  pricing, risk, returns, factors, fixed income, simulation, or any numerical
  finance computation producing files.
---

# Quantitative finance tasks

Only files written to the output directory are graded. Text in the transcript is
never graded. A correct number that is not in the right file, column, or format
scores nothing.

## Execution

1. Identify the exact quantity being asked for.
2. Extract variables, units, time basis, conventions, and constraints.
3. Select the appropriate model/formula before plugging in numbers.
4. Convert units and rates explicitly.
5. Compute carefully, using code/tooling where useful.
6. Sanity-check magnitude, sign, units, and edge cases.
7. Verify the result independently when practical.
8. Match the required output format exactly.
9. Only then provide the final answer.

## Orient before coding

The working directory is `/app`. Inputs are usually under `/app/data/`, outputs
usually go to `/app/output/` or `$OUTPUT_DIR` (default `./output`, which is the
same directory). Create the output directory if it does not exist.

List the input directory and confirm the actual filenames. Do not trust a path
quoted in the task text without checking it on disk; names and extensions
sometimes differ. Load each input and print its shape, columns, dtypes, date
range, and null counts before writing any analysis code.

Work offline with the preinstalled stack (Python, numpy, scipy, pandas). Do not
install packages or fetch anything over the network.

## Extract the spec

Before choosing a method, write down from the task text:

- The exact output path, filename, and file type for every required artifact.
- Exact column names, column order, row count, sort order, and index handling.
- Units and time basis: decimal vs percent, basis points, per period vs
  annualized, calendar vs trading days, and the periods-per-year the task implies.
- Conventions: compounding (simple, discrete, continuous), day count, sign of
  losses and cash flows, inclusive vs exclusive tail cutoffs, eligibility and
  null-handling rules, look-ahead restrictions.
- Rounding: apply the task's rounding only when writing the artifact.
- Seeds and the exact generator calls, when the task prescribes them. Reproduce
  the prescribed order of draws; do not substitute an equivalent-looking one.

If a needed detail is genuinely absent, pick the most standard interpretation,
record it in a short code comment, and continue. Do not silently invent a rule,
and do not stall on it.

## Compute in a script

Write a script to a file and run it. Do not do multi-step arithmetic in your
head, and do not paste long intermediate tables into the transcript.

Use code for anything iterative or error-prone: root-finding, optimization,
calibration, simulation, matrix algebra, regressions, rolling windows.

Keep raw precision throughout. Round only at the write step, and only as
specified.

Convert once, explicitly, near the top: percent to decimal, annual to periodic,
basis points to decimal. Name variables with their unit and basis so a mismatch
is visible. Preserve the sign convention of losses, cash flows, and positions
end to end.

Re-run the whole script after any change rather than patching numbers by hand.

## Verify before finishing

Read back each written file and check it against the spec: it exists at the
required path, has the exact columns in the required order, the expected row
count, the required sort, no unintended index column, and no unexpected nulls.

Sanity-check the numbers: correct sign, plausible magnitude, units consistent
with the requested quantity, and monotonicity or ordering that theory requires
(for example a higher confidence level giving a larger tail risk measure).

Where practical, confirm one result a second way — a closed form against a
simulation, an identity, a small hand-checkable subset, or a limiting case.

If a check fails, fix the cause in the script and re-run. Do not hand-edit an
output file.

Finish only when every required artifact exists and passes these checks. If the
budget is running out, make sure each required file exists with correctly shaped
content rather than leaving some missing.

## Do not

- Report a result you have not read back from the written file.
- Round intermediate values, or apply rounding the task did not ask for.
- Add commentary, extra columns, or extra files the task did not request.
- Mix percent and decimal, or annual and periodic, in the same expression.
- Assume a column exists, a file path is correct, or data is clean without checking.
- Keep iterating once the artifacts are written and verified.
