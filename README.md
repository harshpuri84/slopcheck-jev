# slopcheck

Report which AI tells a passage contains, with the line quoted. Runs as a Claude Code
`Stop` hook, so it checks Claude's own output after every turn.

It never answers "did AI write this". It answers "line 4 is a binary contrast, p=0.91".

```
$ slopcheck draft.md
slopcheck draft.md  4 findings in 61 words
     L1 lex banned word: pivotal  (unslop 7, 'pivotal' at column 20)
        > The launch marks a pivotal moment for the team.
        Use the plain word.
     L1 jev importance puffery  (unslop 1, p=0.94, line picked with confidence 0.75)
        > The launch marks a pivotal moment for the team.
        State the fact. Delete the claim about its importance.
     L2 jev binary contrast  (unslop 9, p=0.97, line picked with confidence 1.00)
        > It is not just faster, but a testament to good design.
        State the second half directly and delete the first.
     L4 jev fake-profound kicker  (no-ai-slop, p=0.90, line picked with confidence 1.00)
        > Ultimately, it is about trust.
        Delete it. End on the clearest concrete sentence already present.
1233 ms, 2 Jev call(s), $0.000120
```

## How it works

Three layers. Code finds, the model judges, code decides.

| Layer | Owns | Cost | Latency |
|---|---|---|---|
| Lex, regex | 7 mechanical tells and a 51-word banned list | $0 | ~3 ms |
| Judge, [Jev](https://typesafe.ai) | 15 tells that need reading | $0.18 / 1,000 passages | 620 ms clean, 1,250 ms dirty |
| Gate, code | Every threshold | $0 | 0 ms |

Jev is a System One model. It returns typed answers and probabilities instead of text.

**Lex** handles em dashes, curly quotes, title-case headings, decorative emoji, boldface
density, inline-header lists and banned words. String matching, so it is exact and free.
Jev never sees these.

**Judge** makes two calls, and the second usually does not run:

1. Fifteen `noul` questions over the whole passage, in parallel. "Does this passage contain
   a binary contrast." One round trip.
2. For each tell that fired, one `choice` over the numbered sentences. "Which line is it."

Call 2 is a selection, not a generation. The options are exactly the sentences the splitter
produced, so a quoted line is always a line that exists in the source. The model cannot
invent a quote.

**Gate** owns every threshold. A `noul` between 0.40 and 0.60 means the model is not
answering, so it is suppressed rather than reported as a weak yes. Change a threshold in
`slopcheck/tells.yaml` and nothing re-runs.

The model is never asked whether a human should care. That is policy, and policy lives in
code.

## Install

```bash
git clone https://github.com/<you>/slopcheck && cd slopcheck
pip install -e .
echo 'TYPESAFE_API_KEY=...' > .env      # from console.typesafe.ai/settings/keys
slopcheck bench/corpus/dirty-01.md
```

Without a key it still runs. `--no-jev` gives the regex layer alone, no network.

For the Claude Code hook, see [hooks/INSTALL.md](hooks/INSTALL.md).

## The tells

Fifteen semantic tells and seven mechanical ones, taken from two skills:
[`unslop`](https://github.com/cursor/plugins/tree/main/pstack) (31 numbered tells) and
`no-ai-slop`. Each finding cites which one it came from.

They live in `slopcheck/tells.yaml`: the question text, the criteria the model answers
against, the threshold, and the fix. That file is the whole domain. Swap it to detect
something else.

## Measurements

Two sets. Neither is large. Sample sizes are printed because the numbers do not mean much
without them.

### Synthetic fixtures, 6 passages

`bench/corpus/`. Written for this repo with tells planted deliberately, so the labels are
known by construction. This tests the plumbing, not human judgment.

Found 13 of 16 planted tells. The three misses:

| Tell | p | Threshold | What happened |
|---|---|---|---|
| `summary_recap_ending` | 0.440 | 0.70 | Undecided band. The model declined to answer |
| `hidden_actor_passive` | 0.490 | 0.70 | Undecided band. Declined |
| `forced_triad` | 0.210 | 0.70 | A flat no. The model disagreed that the triad was padded |

Two of the three are the band doing its job: saying "I do not know" instead of guessing.
`forced_triad` is a genuine weakness and the question wording needs work.

One flagged line in a fixture labelled clean turned out to be a real binary contrast
("Panel count is not the metric. Time from page to first useful graph is"). The label was
wrong, not the detector.

### Real drafts, 9 passages, 221 sentences

A private set of LinkedIn drafts, so it is not in this repo.

**The regex layer found nothing. Zero findings across all nine passages.** Those drafts had
already been through an `unslop` pass, so no em dash, banned word or curly quote survived.
On text that has already been cleaned mechanically, every remaining tell is semantic. That
is the case for a model doing this job rather than a word list.

**Jev found 17.** Thirteen in unedited drafts, four in published text the author had already
hand-edited. Those four are candidate false positives, which is what adjudication is for.

Two of the true positives were lines the author had independently cut from the published
version: "The part worth reading is not the launch post" and "You can grade a Choice".

## Benchmark method

Three arms over the same sentences.

| Arm | What it is |
|---|---|
| A | Lex only. Regex, no model |
| B | Lex + Jev |
| C | Claude reading the whole `no-ai-slop` skill in detect mode |

Labels come from **pooled adjudication**. Every arm runs, the union of what they flagged
becomes the pool, and a human marks each pooled row true or false. The sheet does not show
which arm flagged a row.

Two constraints on reading the results:

**Recall is recall against the pool.** A tell that every arm missed is invisible. This is
the standard limitation of pooled evaluation and it is not fixable without exhaustive
labelling.

**Arm C is not a like-for-like comparison.** It is a prompt to a frontier model, not a
program. It reads the full 31-tell skill on every call and thinks in text. The question it
answers is "do the two agree on the same lines", not "which is faster". The latency and
cost columns are in the table because they are true, not because they settle anything.

The model must not write the labels. Arm C is Claude; if Claude also wrote the ground
truth, arm C would be scored against its own opinion and would win by construction.

```bash
python bench/extract.py      # build the sheet from your own corpus
python bench/run_arms.py     # arms A and B
python bench/run_skill.py    # arm C, needs a working `claude -p`
python bench/pool.py         # build the adjudication sheet
# mark each row y or n in bench/local/adjudicate.tsv
python bench/score.py
```

## Limits

- Typed output guarantees the shape of an answer, not that it is right.
- The thresholds in `tells.yaml` are starting points. Tune them on your own text.
- Sentence splitting is regex. It over-glues after an abbreviation that really did end a
  sentence.
- `forced_triad` and `hidden_actor_passive` under-fire. Known, unfixed.
- Two Jev judgments can disagree: call 1 fires and call 2 names no line. Those are reported
  at passage level and sorted last, never as a confident finding.
- A pin below `locate_min_confidence` is reported with the line but labelled weak. Choice
  confidence measures how spread the distribution is, not whether the top pick is right, so
  a weak pin is often still the correct line.
- It flags quoted examples. A document that discusses a tell, including this README, gets
  flagged for containing it. There is no way for the model to tell an example from a
  lapse without being told which is which.

## Licence

MIT.
