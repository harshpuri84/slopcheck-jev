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

Two layers. Code finds what a regex can settle, one Jev call judges the rest, code decides.

| Layer | Owns | Cost | Latency |
|---|---|---|---|
| Lex, regex | 18 tells: patterns, word lists, phrase lists, density, length | $0 | ~6 ms |
| Judge, [Jev](https://typesafe.ai) | 15 tells that need reading | $0.105 / 1,000 | ~575 ms |
| Gate, code | Every threshold | $0 | 0 ms |

Jev is a System One model. It returns typed answers and probabilities instead of text.

**Lex** handles anything a regex can settle: em dashes, curly quotes, title-case headings,
decorative emoji, inline-header lists, boldface density, sentence length, stacked hedging,
and six word or phrase lists. Exact, free, and it quotes the line, because a regex knows
where it matched.

**Judge** is one call. Fifteen `noul` questions over the whole passage, in parallel, and
they cannot see each other's answers. It reports which tells are present and with what
probability. It does not report which line, and that is deliberate: see below.

**Gate** owns every threshold. A `noul` between 0.40 and 0.60 means the model is not
answering, so it is suppressed rather than read as a weak yes. Change a threshold in
`slopcheck/tells.yaml` and nothing re-runs.

The model is never asked whether a human should care. That is policy, and policy lives in
code.

### Why it does not quote the line

The first version did. It made a second call that pinned each tell to a sentence, choosing
from lines the splitter produced so it could not fabricate a quote.

Deleting that made the detector better on every axis:

| | With line location | Without |
|---|---|---|
| Precision | 0.80 | **0.95** |
| F1 | 0.44 | **0.62** |
| Latency per passage | 1,365 ms | **575 ms** |
| Cost per 1,000 | $0.485 | **$0.105** |
| Jev calls | 1 to 6 | Always 1 |
| Lines of Python | ~760 | **564** |

Precision went up when the feature came out. The location layer was adding false positives,
not only latency.

The deeper reason it had to go: Jev returns typed answers, not text, which is why its output
is free. It cannot hand back a list of findings with quotes, because that is generation. The
only way to get a sentence was a second round of typed questions about lines, and that one
sentence cost 774 ms, 4.6x the tokens, and every defect the detector had. A cap that could
only report one instance per tell. A per-line question that fired on 25 of 47 lines once the
cap was lifted. Batching, thread pools, and a second vocabulary of questions to maintain.

The requirement came from `no-ai-slop`'s detect mode, which quotes lines because a frontier
model writing prose can. It was never a requirement of this tool.

## Demo

```bash
python -m slopcheck.serve        # http://localhost:8781
```

A local page that shows what Jev returns, not just what slopcheck concludes: all fifteen
probabilities, the threshold on each bar, and the 0.40 to 0.60 strip where the model is
declining to answer. The key stays in the server process; the browser never sees it.

It makes two requests, matching the two calls, so the architecture is visible rather than
hidden behind one spinner. Call 1 fills fifteen bars at once in roughly 600 ms. Call 2 runs
only when something fired, and the header says "no call 2 needed" when nothing did.

Six one-click samples, three dirty and three clean, plus a text box. `dirty-02` fires
eleven of the fifteen.

The design test this had to pass, from the author's own spec: would the demo look identical
with a cheap fast LLM behind it? A page that lists AI tells would. Fifteen calibrated
probabilities landing together, with a visible band where the model refuses, would not.

## The tells

Fifteen semantic tells and seven mechanical ones, taken from two skills:
[`unslop`](https://github.com/cursor/plugins/tree/main/pstack) (31 numbered tells) and
`no-ai-slop`. Each finding cites which one it came from.

They live in `slopcheck/tells.yaml`: the question text, the criteria the model answers
against, the threshold, and the fix. That file is the whole domain. Swap it to detect
something else.

### Coverage against unslop's 31

28 of 31. The three gaps need judgment about the world rather than about the sentence, and
each would add a question to call 1 for every passage, so they are left out on purpose.

| # | unslop tell | slopcheck | layer |
|---|---|---|---|
| 1 | Puffery | `importance_puffery` | jev |
| 2 | Name-dropping | not covered | n/a |
| 3 | Superficial -ing phrases | `superficial_ing` | jev |
| 4 | Promotional language | `promotional` | lex |
| 5 | Vague attributions | `weasel_attribution` | jev |
| 6 | Formulaic challenges | not covered | n/a |
| 7 | AI vocabulary | `banned_word` | lex |
| 8 | Fancy ways to say "is" | `fake_strong_verb` | jev |
| 9 | "Not just X, but Y." | `binary_contrast` | jev |
| 10 | Rule of three | `forced_triad` | jev |
| 11 | Synonym cycling | `synonym_cycling` | jev |
| 12 | False ranges | not covered | n/a |
| 13 | Em dash overuse | `em_dash`, `en_dash_sub` | lex |
| 14 | Colon overuse | `colon_reveal` | jev |
| 15 | Boldface overuse | `bold_density` | lex |
| 16 | Inline-header lists | `inline_header_list` | lex |
| 17 | Title case headings | `title_case_heading` | lex |
| 18 | Decorative emojis | `decorative_emoji` | lex |
| 19 | Curly quotes | `curly_quote` | lex |
| 20 | Chatbot phrases | `chatbot_phrase` | lex |
| 21 | Cutoff disclaimers | `cutoff_disclaimer` | lex |
| 22 | Sycophantic tone | `sycophancy` | lex |
| 23 | Filler phrases | `filler_phrase`, `throat_clearing` | lex |
| 24 | Excessive hedging | `hedge_stack` | lex |
| 25 | Generic conclusions | `summary_recap_ending` | jev |
| 26 | Abstract metaphor nouns | `abstract_metaphor` | lex |
| 27 | Say what it does, not how it feels | `feeling_not_mechanism` | jev |
| 28 | Shorten or split dense sentences | `long_sentence` | lex |
| 29 | Active voice | `hidden_actor_passive` | jev |
| 30 | Cut adverbs, or use a stronger verb | `empty_adverb` | lex |
| 31 | Prefer the plain word | `plain_word` | lex |

## Measurements

Two sets. Neither is large. Sample sizes are printed because the numbers do not mean much
without them.

### Synthetic fixtures, 6 passages

`bench/corpus/`. Written for this repo with tells planted deliberately, so the labels are
known by construction. This tests the plumbing, not human judgment.

Found 16 of 16 planted tells, plus 8 flags for tells that were not planted.

The first pass found 13 of 16. Three questions were rewritten to fix it, and the numbers
moved a long way:

| Tell | p before | p after | What was wrong with the question |
|---|---|---|---|
| `summary_recap_ending` | 0.40 | 0.96 | It asked whether the closing "adds anything new". A closing can summarise and still state a claim |
| `forced_triad` | 0.22 | 0.86 | It asked whether the third item was "padding". It now asks whether the three items are peers |
| `hidden_actor_passive` | 0.51 | 0.90 | It did not say what a passive is, so an impersonal subject read as one |

`hidden_actor_passive` then fired on all three clean fixtures, so the question names the
active cases explicitly and its threshold is 0.80 rather than 0.70. It is the noisiest
tell here.

The 8 extra flags are mostly real. The dirty fixtures carry more tells than were planted:
"In conclusion, retries are a design decision, not an accident" is both a summary-recap
ending and a binary contrast. One flag on a fixture labelled clean was also correct
("Panel count is not the metric. Time from page to first useful graph is"). That label was
wrong, not the detector.

These questions were tuned against these six fixtures only, never against the private
corpus below, so the benchmark labels stay uncontaminated.

### Real drafts, 9 passages

A private set of LinkedIn drafts, so the text is not in this repo. The author adjudicated
all 45 pooled rows: 43 confirmed tells, 2 false positives.

| Arm | TP | FP | FN | Precision | Recall* | F1 | ms/passage | $/1,000 |
|---|---|---|---|---|---|---|---|---|
| A, regex only | 2 | 1 | 41 | 0.67 | 0.05 | 0.09 | 6 | $0 |
| B, regex + Jev | 20 | 1 | 23 | **0.95** | 0.47 | 0.62 | **575** | **$0.105** |
| C, Claude + no-ai-slop | 33 | 1 | 10 | 0.97 | 0.77 | 0.86 | 21,387 | not measurable |

`*` recall against the pool. n = 45 rows, 43 positives.

**On precision the two are level: 0.95 against 0.97.** When Jev speaks it is almost always
right. It finds 61% of what the frontier model finds, 37 times faster, for a tenth of a cent
per thousand passages.

**Arm C is better at the task and cannot do the job.** 21 seconds per passage cannot run in
a `Stop` hook after every turn. The first version of this README scored the two on F1 as if
they were interchangeable and never applied the constraint the tool exists under. Under a
two-second budget, arm C is not eligible.

The regex layer found almost nothing, as on the synthetic set: these drafts had already been
through an `unslop` pass, so no em dash, banned word or curly quote survived. Two of its
three findings were correct.

### What changed between versions

| Version | Precision | Recall* | F1 | ms |
|---|---|---|---|---|
| Two calls, one line per tell | 0.80 | 0.31 | 0.44 | 1,365 |
| Two calls, every line per tell | not scored, flagged 25 of 47 lines in one passage | | | 1,404 |
| One call, no lines | **0.95** | **0.47** | **0.62** | **575** |

The middle row is the interesting failure. Lifting the one-line cap meant asking a
passage-level question per line wrapped in "consider only line N", and the model kept
answering about the passage. Writing eleven separate per-line questions fixed it, and then
the whole layer came out anyway.

## Benchmark method

Three arms over the same sentences.

| Arm | What it is |
|---|---|
| A | Lex only. Regex, no model |
| B | Lex + Jev, one call |
| C | Claude reading the whole `no-ai-slop` skill in detect mode |

Scored at passage level: does this passage contain this tell. slopcheck does not claim a
line for a semantic tell, so scoring per line would hold arm B to a claim it never makes.

Labels come from **pooled adjudication**. Every arm runs, the union of what they flagged
becomes the pool, and a human marks each pooled row true or false. The sheet does not show
which arm flagged a row.

Two constraints on reading the results:

**Recall is recall against the pool.** A tell that every arm missed is invisible. This is
the standard limitation of pooled evaluation and it is not fixable without exhaustive
labelling.

**Arm C is not a like-for-like comparison.** It is a prompt to a frontier model, not a
program. It reads the full 31-tell skill on every call and thinks in text. It is also not
eligible for the job this tool does: 21 seconds per passage cannot run after every turn.
Read the table as "how much does the cheap always-on gate miss", not as a race.

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
- It reports which tells a passage contains, not where. For the mechanical tells the
  regex layer still gives you the line; for the fifteen semantic ones you get the tell
  and its probability. See **Why it does not quote the line**.
- `forced_triad` and `hidden_actor_passive` under-fire. Known, unfixed.
- Name-dropping, formulaic challenges and false ranges (unslop 2, 6, 12) are not
  detected at all.
- Two Jev judgments can disagree: call 1 fires and call 2 names no line. Those are reported
  at passage level and sorted last, never as a confident finding.
- A pin below `locate_min_confidence` is reported with the line but labelled weak. Choice
  confidence measures how spread the distribution is, not whether the top pick is right, so
  a weak pin is often still the correct line.
- **It measures presence, not severity.** A tell the writer would happily publish scores
  the same as one they would cut. Adjudicating a real corpus, the author marked nine
  binary contrasts as genuinely present and in the same breath called them "passable for
  posting". A useful tool would rank by how much the line costs, and this one cannot.
- It flags quoted examples. A document that discusses a tell, including this README, gets
  flagged for containing it. There is no way for the model to tell an example from a
  lapse without being told which is which.

## Licence

MIT.
