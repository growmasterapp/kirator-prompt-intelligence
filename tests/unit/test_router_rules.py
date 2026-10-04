"""Unit tests for Stage-1 router keyword / BUG-3 rules (no embeddings required)."""

import pytest

from src.stages.stage1_router.router import RequestRouter

pytestmark = [pytest.mark.unit, pytest.mark.overnight]


@pytest.fixture()
def router():
    # No embedder — keyword path only
    return RequestRouter(embedder=None)


def test_marketing_not_code(router):
    result = router.process("help me with marketing", {})
    assert result.task_category.value != "code_generation"
    assert result.task_category.value in ("business_planning", "creative_writing", "general")


def test_raise_email_not_code(router):
    result = router.process("write me a raise email", {})
    assert result.task_category.value != "code_generation"


def test_python_function_is_code(router):
    result = router.process("write a python function to reverse a string", {})
    assert result.task_category.value == "code_generation"
