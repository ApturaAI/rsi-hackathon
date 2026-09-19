---
name: quant-task-protocol
description: Verified operating procedure for quantitative-finance data and pricing tasks graded by hidden tests. Read the spec into a checklist, inspect data before coding, write one script, self-check every output against the spec, and never finish with a missing file.
---

# Quant task protocol

Hidden tests grade you on files. They check that every required output exists,
has the exact columns and keys the spec lists, and matches reference numbers to
a tolerance. Most failures are not maths errors. They are a missing file, a
wrong path, a misspelled column, a wrong type, or a convention the spec stated
that you did not follow. Work like a build engineer: spec, data, code, verify.

## Phase 0: Spec to checklist (before any code)

1. Read the whole instruction once. Then write `/app/CHECKLIST.md` containing:
   - the output directory (respect `OUTPUT_DIR` if the spec mentions it;
     otherwise the path the spec gives, usually `/app/output/`)
   - every output file name, and for each: every column or JSON key, in order
   - every stated convention: ddof, annualisation factor, risk-free rate,
     sort order, date handling, rounding, sign conventions, units (bps vs
     decimal), day-count
   - every parameter the spec says to take from a params file rather than assume
2. Re-read the spec against the checklist. Anything ambiguous: choose the most
   standard textbook definition and write your choice in the checklist.

## Phase 1: Inspect the data

Run `python3 -c` snippets or a short script to print, for every input file:
shape, columns, dtypes, first 3 rows, date range, NaN count per column,
duplicates on the key columns. Read any `params.json` or glossary fully and
print it. Do not start modelling until you know the data's quirks. Common traps:

- dates as strings, mixed formats, unsorted, duplicated
- prices vs returns, percent vs decimal, bps vs decimal
- tab-separated files with `.tsv`, quoted fields, thousands separators
- a column the spec calls X is named x_1 in the file: use the file's names
  for reading and the spec's names for writing

## Phase 2: Write one script

- Write `/app/solve.py` as a file. Do not pipe long code through `python -c`.
- Build it in sections with a `main()` that runs them in order and writes each
  output as soon as it is ready, so partial progress survives a crash.
- Load parameters from the params file when one exists. Never hard-code a
  value the spec says comes from a file.
- Sort deterministically before any operation whose result depends on order
  (rank, cumulative, rebalance dates, top-N). Break ties by name or ID.
- Use pandas/numpy defaults only when the spec is silent. If the spec states
  `ddof=1`, pass it explicitly everywhere.
- Prefer exact closed forms over simulation when the spec gives a formula.
  When simulation is required, seed exactly as the spec says.
- Keep the script under a few hundred lines per file write. If it grows, split
  into helper modules and import them.

## Phase 3: Verify against the checklist (mandatory)

Run the script, then run `python3 /harbor/skills/*/check_outputs.py <output_dir>`
if that helper is present, or do the same checks by hand:

1. Every file in the checklist exists in the output directory. No extras needed.
2. Each CSV: columns match the checklist exactly (names and set). Print the
   head and the row count and compare with what the spec implies
   (one row per X means the row count equals the number of X).
3. Each JSON: keys match exactly. Values are plain numbers, bools, or strings,
   not numpy types, not NaN, not Infinity. `json.dump` will write NaN and the
   grader will reject it.
4. Sanity ranges: volatility and rates positive, weights sum to 1 where they
   should, drawdown sign as specified, correlations in [-1, 1], probabilities
   in [0, 1], prices non-negative, put-call parity or model-vs-analytic
   differences small where the spec mentions them.
5. Internal consistency flags the spec asks for (`all_checks_passed`,
   `*_ok`) must be computed from your own results, not set to true.
5b. Boundary check every count and every schedule. For any deliverable that is
   a count (rebalances, events, periods, filings) or a date schedule, print the
   full list of events with their dates and compare the first and last against
   the spec's start rule and the parameter file (start day, lookback fill,
   warm-up). Off-by-one at the first or last event is the most common way a
   backtest deliverable misses its tolerance. If the spec says "first N days
   are for signal only", the first trade is on day N+1 and rebalances count
   from there.
6. Re-run the script from scratch once and confirm outputs are identical.
   Non-determinism fails tolerance tests.

Fix and repeat until every line of the checklist is ticked, then do Phase 3b.
Only then stop.

## Phase 3b: Independent recompute (structural OK is not correctness)

`check_outputs.py` only proves the files are well formed. Most failed tasks
have well-formed files with wrong numbers. Before finishing, recompute at least
two key deliverables by a second, independent route and compare:

- a portfolio or strategy return: recompute from the position weights and the
  raw returns in a three-line loop, not from your pipeline's intermediate arrays
- an attribution or decomposition: check that the components sum to the total
  they decompose (allocation + selection + interaction = active return)
- a price or rate from a model: check a limiting case (zero vol, zero rate,
  deep in or out of the money, flat curve) against the closed form
- a fitted model with labelled states or regimes: label by the economic meaning
  the spec gives (for example the high-mean or low-variance state), never by
  the index the fitting library happened to assign, and print the per-state
  statistics to prove the labelling
- a count or schedule: print the first and last three events with dates

If the two routes disagree beyond the spec's tolerance, the pipeline is wrong.
Fix it; do not average or pick one.

## Reading the spec for hidden conventions

Specs in this benchmark are precise. When a phrase admits two readings, the
reference almost always uses the plainest literal one:

- "rebalance monthly" means on the first trading day of each calendar month in
  the trading window; the signal uses data up to and including the prior day
- "transaction cost of c bps" is charged on traded notional at each rebalance:
  cost = c/1e4 × sum(|w_new − w_old|); the first rebalance trades from zero
- "annualised" uses the factor stated; if none, 252 for daily, 12 for monthly,
  52 for weekly; calendar-day maths uses 365 unless a day-count is named
- "z-score cross-sectionally" means per date across assets, ddof as the spec
  says (default ddof=1 for sample statistics, ddof=0 only when stated)
- "top N / bottom N" break ties by the sort order the spec gives, else by
  ticker ascending; sort tickers before any matrix build
- "maximum drawdown" is peak-to-trough on the cumulative return path from the
  first trading day, reported as a positive magnitude unless told otherwise
- allocation, selection, interaction effects follow the Brinson-Fachler
  variant with benchmark total return unless the spec spells out
  Brinson-Hood-Beebower; when in doubt, implement the variant the spec's
  formula shows, symbol by symbol
- random draws use `numpy.random.default_rng(seed)` with the seed from the
  params file; draw in the order the spec lists the simulations
- if the spec mentions `OUTPUT_DIR`, read it with `os.environ.get`; create the
  directory; never hard-code a different path
- JSON numbers must be plain Python `float`/`int`; cast with `float()` and
  never write NaN; CSV columns in the exact order the spec lists them

## Numeric conventions unless the spec overrides

- Sample standard deviation uses `ddof=1`; annualise with the factor the spec
  gives (252 for daily equity by default).
- Sharpe with zero risk-free rate unless a rate is given.
- Max drawdown reported as a positive magnitude if the spec says so; otherwise
  follow the spec's sign exactly.
- Log vs simple returns: use what the spec says; if silent, simple returns for
  portfolio arithmetic, log returns for volatility estimators that state them.
- Round only at output time, and only if the spec asks for it.

## Do not

- Do not write to a path other than the one the spec names.
- Do not leave a placeholder or partial file. An empty file is a failed test.
- Do not stop because the maths is hard. Implement the most standard method,
  verify, and move on.
- Do not spend turns explaining. Spend them checking.
