"""Lex layer tests. No network, no key, no Jev."""
import pathlib
import sys

import yaml

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from slopcheck import lex

CFG = yaml.safe_load((pathlib.Path(__file__).parent.parent
                      / "slopcheck/tells.yaml").read_text())


def tells(text):
    return sorted({h.tell for h in lex.run(text, CFG).hits})


def test_em_dash_caught():
    assert "em_dash" in tells("The team shipped it — on a Friday, of all days.")


def test_em_dash_inside_code_ignored():
    assert "em_dash" not in tells("Run `build --a—b` to continue with the process.")


def test_em_dash_inside_url_ignored():
    assert "em_dash" not in tells("See https://example.com/a—b for the full writeup.")


def test_banned_word_caught():
    assert "banned_word" in tells("This will streamline the pipeline for everyone.")


def test_banned_word_needs_word_boundary():
    # "foster" is banned. "Fostercare" as one word is not the banned word.
    assert "banned_word" not in tells("The Fostercare module ships on Tuesday next week.")


def test_inline_header_list_caught():
    assert "inline_header_list" in tells("- **Performance:** performance improved a lot.")


def test_bold_lead_in_with_period_is_allowed():
    # unslop 16 says this form is fine, not a tell.
    assert "inline_header_list" not in tells(
        "- **Schema in TypeScript.** Tables live in one file.")


def test_title_case_heading_caught():
    assert "title_case_heading" in tells("## This Is A Title Case Heading")


def test_sentence_case_heading_allowed():
    assert "title_case_heading" not in tells("## This is a sentence case heading")


def test_units_are_numbered_in_order():
    units = lex.run("First one here. Second one here.\n\nThird one here.", CFG).units
    assert [u.n for u in units] == [1, 2, 3]


def test_abbreviation_does_not_split_a_sentence():
    units = lex.run("Dr. Chen shipped it on 24 Sep at 09:00 sharp.", CFG).units
    assert len(units) == 1


def test_quote_restores_code_stripped_for_matching():
    u = lex.run("Run `npm run build` and then check the output.", CFG).units[0]
    assert "`npm run build`" in u.raw      # the human sees the code
    assert "npm" not in u.text             # Jev does not


def test_chatbot_phrase_caught():
    assert "chatbot_phrase" in tells("Done. I hope this helps with the rollout plan.")


def test_sycophancy_caught_once_not_twice():
    t = [h.tell for h in lex.run("Great question! Here is the answer you wanted.", CFG).hits]
    assert t.count("sycophancy") == 1
    assert "chatbot_phrase" not in t


def test_every_occurrence_of_a_phrase_is_reported():
    hits = [h for h in lex.run(
        "In order to ship, we refactored in order to cut the build time.", CFG).hits
        if h.tell == "filler_phrase"]
    assert len(hits) == 2


def test_stacked_hedging_caught():
    assert "hedge_stack" in tells(
        "It could potentially possibly be argued that the change helped.")


def test_single_hedge_allowed():
    assert "hedge_stack" not in tells("This might be the cause of the regression.")


def test_boldface_density_is_document_level():
    dense = "**one** **two** **three** " + "word " * 20
    assert "bold_density" in tells(dense)
    assert "bold_density" not in tells("**one** " + "word " * 60)


def test_long_sentence_caught():
    long = " ".join(["word"] * 45) + "."
    assert "long_sentence" in tells(long)
    assert "long_sentence" not in tells(" ".join(["word"] * 20) + ".")


def test_promotional_and_metaphor_cite_their_own_rule():
    by = {h.tell: h.unslop for h in lex.run(
        "The seamless flywheel is a world-class primitive here.", CFG).hits}
    assert by.get("promotional") == 4
    assert by.get("abstract_metaphor") == 26


def test_empty_adverb_caught():
    assert "empty_adverb" in tells("The change significantly improved the throughput.")


def test_quote_windows_around_a_late_match():
    line = "x" * 180 + " the flywheel is here " + "y" * 40
    h = [x for x in lex.run(line, CFG).hits if x.tell == "abstract_metaphor"]
    assert len(h) == 1
    assert "flywheel" in h[0].quote          # the reader can see the problem
    assert h[0].quote.startswith("...")      # and knows text was cut


def test_two_occurrences_on_one_line_quote_differently():
    line = "The moat is here. " + "z" * 150 + " and another moat at the end."
    q = [x.quote for x in lex.run(line, CFG).hits if x.tell == "abstract_metaphor"]
    assert len(q) == 2
    assert q[0] != q[1]
