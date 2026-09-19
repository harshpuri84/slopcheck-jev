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
| Lex, regex | 18 tells: patterns, word lists, phrase lists, density, length | $0 | ~6 ms |
| Judge, [Jev](https://typesafe.ai) | 15 tells that need reading | $0.18 / 1,000 passages | 620 ms clean, 1,250 ms dirty |
| Gate, code | Every threshold | $0 | 0 ms |

Jev is a System One model. It returns typed answers and probabilities instead of text.

**Lex** handles anything a regex can settle: em dashes, curly quotes, title-case headings,
decorative emoji, inline-header lists, boldface density, sentence length, stacked hedging,
and six word or phrase lists (AI vocabulary, promotional language, abstract metaphor nouns,
filler phrases, chatbot phrases, sycophantic openers, often-empty adverbs). Exact and free.
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

### Coverage against unslop's 31

28 of 31. The three gaps need judgment about the world rather than about the sentence, and
each would add a question to call 1 for every passage, so they are left out on purpose.

| # | unslop tell | slopcheck | layer |
|---|---|---|---|
| 1 | Puffery | `importance_puffery` | jev |
| 2 | Name-dropping | not covered | — |
| 3 | Superficial -ing phrases | `superficial_ing` | jev |
| 4 | Promotional language | `promotional` | lex |
| 5 | Vague attributions | `weasel_attribution` | jev |
| 6 | Formulaic challenges | not covered | — |
| 7 | AI vocabulary | `banned_word` | lex |
| 8 | Fancy ways to say "is" | `fake_strong_verb` | jev |
| 9 | "Not just X, but Y." | `binary_contrast` | jev |
| 10 | Rule of three | `forced_triad` | jev |
| 11 | Synonym cycling | `synonym_cycling` | jev |
| 12 | False ranges | not covered | — |
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

### Real drafts, 9 passages, 221 sentences

A private set of LinkedIn drafts, so it is not in this repo.

**The regex layer found nothing. Zero findings across all nine passages.** Those drafts had
already been through an `unslop` pass, so no em dash, banned word or curly quote survived.
On text that has already been cleaned mechanically, every remaining tell is semantic. That
is the case for a model doing this job rather than a word list.

**Jev found 20.** Fifteen in unedited drafts, five in published text the author had already
hand-edited. Those five are candidate false positives, which is what adjudication is for.

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
- Name-dropping, formulaic challenges and false ranges (unslop 2, 6, 12) are not
  detected at all.
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
