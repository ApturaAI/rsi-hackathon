---
name: exact-answer-protocol
description: How to answer one expert-level question so a strict judge marks it correct. Pin down exactly what form the answer must take, compute rather than recall whenever the sandbox can compute it, verify by an independent route, commit to one exact final answer, and write the answer file early and again after every refinement.
---

# Exact answer protocol

A strict judge compares one extracted final answer with a reference. It marks
anything ambiguous, hedged, or in the wrong form as wrong. Two answers joined
by "or" are wrong. A correct number in the wrong unit or form is wrong. A
brilliant explanation with no clear final answer is wrong. Your whole job is
one exact final answer in the exact format the task specifies, written to the
answer file.

## Mechanics that lose tasks

- The answer file is the only thing graded. Write it with the file tool in
  the format the task shows, and write it early: a first version within your
  first few turns, then overwrite it whenever you improve the answer. An empty
  or missing file scores zero no matter how good your reasoning was.
- Keep the explanation to a few sentences. Long explanations do not score and
  burn the turns you need for checking.
- Do not spend turns exploring the container. There is nothing to find except
  the question and any files it names.

## Step 1: Pin the target before solving

Write down, in a `think` call, exactly what the question asks for:

- the object (a number, a name, a letter, an expression, a sequence, a word)
- the form (integer, decimal to n places, fraction, closed form, units,
  scientific notation, a chemical name or formula or notation, a specific
  string case)
- the scope (count of what, over which range, under which assumptions stated
  in the question)
- for multiple choice: the exact option letter, and whether more than one
  can be correct

Then check the last sentence of the question again. Questions often state
the required form at the end.

## Step 2: Compute instead of recalling

The sandbox has Python. Anything countable, decodable, simulable, or
algebraic should be computed, not estimated:

- ciphers, permutations, encodings, string puzzles: write the decoder or
  brute-force the key space
- counting, probability, combinatorics, recurrences: enumerate or compute
  exactly with integers or fractions, not floats
- physics, chemistry, engineering numbers: carry units explicitly, compute
  with the stated constants, round only at the end to the precision asked
- algorithms and complexity: implement the small case and count operations
  or verify the claimed bound on concrete inputs
- structures and formulas: derive the formula from the parts and check mass
  balance or valence

Write the script to a file, run it, print intermediate values. If the script
errors, fix it; do not fall back to a guess.

## Step 3: Verify by an independent route

Before finalising, do one check that does not reuse the same reasoning:

- back-substitute the answer into the question's conditions
- recompute with a different method (closed form vs simulation, dimensional
  analysis vs direct calculation)
- for a decoded text, check that it reads as fluent text and that every
  symbol maps consistently
- for multiple choice, eliminate each other option explicitly and make sure
  none of the "wrong" options is equally valid under the question's wording
- for a numeric answer, check magnitude and sign against physical or logical
  bounds

If the check fails, the answer is wrong. Find the error rather than choosing
between two candidates.

## Step 4: Commit and format

- One final answer. Never "A or B", never a range unless the question asks
  for a range, never "approximately" unless the form allows it.
- Match the requested form exactly: same units, same precision, same
  notation, option letter for multiple choice (with the option text after it
  if that helps the judge, but the letter first).
- Simplify fully: reduced fractions, simplified radicals, canonical names.
- If the question implies an integer, give an integer.
- Confidence is a plain percentage. Give a calibrated number; it is
  extracted, not scored, so do not let it distract you.

## When you cannot solve it fully

Still answer. A specific best answer scores when it happens to be right; a
refusal never does. Narrow to the single most likely candidate using the
constraints you did establish, state it as the final answer, and set a lower
confidence. Do not write "unknown" or "cannot be determined" unless the
question itself asks whether something is determinable.
