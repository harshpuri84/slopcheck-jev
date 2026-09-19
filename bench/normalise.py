"""Map every arm's tell names onto one vocabulary.

Arm B emits slopcheck's ids. Arm C emits whatever the model typed, which is not
stable: it produced both "Binary contrast" and "Binary contrasts" in one run. Without
this, the same flagged line becomes two pool rows and neither arm gets credit for
agreeing with the other.

Tells only one arm can find keep an arm-specific id, so the pool shows them rather
than hiding them.
"""
import re

CANON = {
    "binary contrast": "binary_contrast",
    "negative listing": "negative_listing",          # no-ai-slop only, B has no tell
    "dramatic fragmentation": "dramatic_fragmentation",   # no-ai-slop only
    "robotic rhythm": "robotic_rhythm",              # no-ai-slop only
    "untangled sentence robotic rhythm run on": "robotic_rhythm",
    "faux insight setup": "faux_insight",
    "often empty adverb": "empty_adverb",
    "fake profound kicker": "fake_profound_kicker",
    "colon reveal": "colon_reveal",
    "rhetorical setup": "rhetorical_setup",
    "summary recap ending": "summary_recap_ending",
    "throat clearing opener": "throat_clearing",
    "importance puffery": "importance_puffery",
    "weasel attribution": "weasel_attribution",
    "fake strong verb": "fake_strong_verb",
    "superficial analysis": "superficial_ing",
    "superficial ing clause": "superficial_ing",
    "synonym cycling": "synonym_cycling",
    "feeling instead of mechanism": "feeling_not_mechanism",
    "forced rule of three": "forced_triad",
    "rule of three": "forced_triad",
    "passive with hidden actor": "hidden_actor_passive",
    "em dash": "em_dash",
    "em dashes": "em_dash",
    "formatting slop": "formatting_slop",
    "words to cut": "banned_word",
    "ai vocabulary": "banned_word",
    "promotional language": "promotional",
    "abstract metaphor noun": "abstract_metaphor",
    "filler phrase": "filler_phrase",
    "chatbot phrase": "chatbot_phrase",
    "sycophantic opener": "sycophancy",
    "cutoff disclaimer": "cutoff_disclaimer",
    "stacked hedging": "hedge_stack",
    "excessive hedging": "hedge_stack",
    "boldface overuse": "bold_density",
    "dense sentence": "long_sentence",
    "fancier word than needed": "plain_word",
    "inline header list": "inline_header_list",
    "title case heading": "title_case_heading",
    "curly quote": "curly_quote",
    "decorative emoji": "decorative_emoji",
}


def canon(name):
    """Lowercase, drop the ': word' suffix slopcheck adds, singularise, then map."""
    s = name.split(":")[0].strip().lower()
    s = re.sub(r"[^a-z ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if s.endswith("s") and s[:-1] in CANON:
        s = s[:-1]
    s = re.sub(r"\b(\w+)s\b", lambda m: m.group(1) if m.group(1) in
               " ".join(CANON).split() else m.group(0), s) if s not in CANON else s
    if s in CANON:
        return CANON[s]
    sing = s[:-1] if s.endswith("s") else s
    if sing in CANON:
        return CANON[sing]
    return "x_" + sing.replace(" ", "_")
