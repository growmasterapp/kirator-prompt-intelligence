"""Unit tests for composer anti-hallucination heuristics."""

import pytest

from src.stages.stage6_prompt_composer.composer import _find_invented_details

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_flags_invented_salary():
    original = "write me a raise email"
    prompt = "Ask for a raise from $120,000 to $145,000 at Acme Corp."
    flags = _find_invented_details(prompt, original)
    assert any("dollar" in f.lower() or "name" in f.lower() for f in flags)


def test_allows_details_present_in_request():
    original = "write a raise email asking for $120000"
    prompt = "Compose an email requesting a raise to $120000."
    flags = _find_invented_details(prompt, original)
    assert not any("dollar" in f.lower() for f in flags)


def test_flags_tech_on_non_code_request():
    original = "help me with marketing"
    prompt = "Use OAuth and JWT to authenticate the campaign API."
    flags = _find_invented_details(prompt, original)
    assert any("technology" in f.lower() for f in flags)
