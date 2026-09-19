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
