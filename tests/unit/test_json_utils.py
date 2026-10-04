"""Unit tests for LLM JSON extraction / repair."""

import json

import pytest

from src.core.json_utils import extract_json, parse_json_with_retry

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


def test_extract_strips_code_fence():
    raw = '```json\n{"clarity_structure": {"score": 4}}\n```'
    cleaned = extract_json(raw)
    data = json.loads(cleaned)
    assert data["clarity_structure"]["score"] == 4


def test_extract_strips_think_tags():
    raw = '<think>noisy</think>{"a": 1}'
    cleaned = extract_json(raw)
    assert json.loads(cleaned)["a"] == 1


def test_extract_trailing_comma():
    raw = '{"score": 3,}'
    cleaned = extract_json(raw)
    assert json.loads(cleaned)["score"] == 3


def test_parse_json_with_retry_ok():
    data = parse_json_with_retry('{"weaknesses": ["x"], "improvements": ["y"]}')
    assert data["weaknesses"] == ["x"]
