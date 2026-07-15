"""
Shared JSON extraction utilities.

Consolidates the duplicate _extract_json() logic that was scattered across
Stages 2, 3, 4, and 7 into a single, robust implementation.

v2 — added: unquoted-key repair, single-quote normalization, control-char
stripping, aggressive bracket-matching fallback.
"""

import json
import re
import logging

logger = logging.getLogger(__name__)

# Patterns that DeepSeek-R1 and other models wrap around JSON
_THINKING_BLOCK_RE = re.compile(
    r"__(?:START|END)\s*THINKING__", re.DOTALL
)
_CODE_FENCE_OPEN_RE = re.compile(r"```(?:json)?\s*")
_CODE_FENCE_CLOSE_RE = re.compile(r"```\s*$")
_THINKING_EMOJI_RE = re.compile(r"[\U0001f9ec].*?[\U0001f4a4]", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

# Invisible Unicode characters that can break JSON parsing
_INVISIBLE_CHARS_RE = re.compile(
    r"[\ufeff\u200b\u200c\u200d\u200e\u200f\ufeff\u00a0\r]"
)

# Control characters that break JSON (keep \n and \t)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def extract_json(raw: str) -> str:
    """Extract and clean JSON from potentially noisy LLM output.

    Handles common LLM artifacts:
      - ```json` / ``` code fences
      - __START/END THINKING__ blocks (DeepSeek-R1)
      - Emoji thinking markers (DeepSeek-R1 with emoji mode)
      - Trailing commas before } or ]
      - Extra text before/after the JSON object
      - Invisible Unicode characters (BOM, zero-width spaces, etc.)
      - Unquoted keys (common with small models)
      - Single quotes instead of double quotes
      - Control characters inside strings

    Returns the cleaned JSON string ready for ``json.loads()``.
    """
    text = raw.strip()

    # Strip invisible Unicode characters FIRST (before any other processing)
    text = _INVISIBLE_CHARS_RE.sub("", text)

    # Strip markdown code fences
    text = _CODE_FENCE_OPEN_RE.sub("", text)
    text = _CODE_FENCE_CLOSE_RE.sub("", text)

    # Strip thinking blocks
    text = _THINKING_BLOCK_RE.sub("", text)
    text = _THINKING_EMOJI_RE.sub("", text)
    text = text.strip()

    # Find the outermost JSON object
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        json_str = text[start : end + 1]
    else:
        logger.warning("extract_json: no JSON object found in LLM output")
        return text

    # Fix trailing commas (very common with DeepSeek-R1)
    json_str = _TRAILING_COMMA_RE.sub(r"\1", json_str)

    # Strip control characters (except \n, \t)
    json_str = _CONTROL_CHARS_RE.sub("", json_str)

    # Fix single quotes -> double quotes ONLY if no double quotes present
    # (avoids breaking legitimate JSON that contains single quotes in values)
    if '"' not in json_str and "'" in json_str:
        json_str = json_str.replace("'", '"')

    return json_str


def _try_repair_json(json_str: str) -> str | None:
    """Attempt increasingly aggressive JSON structural repairs.

    Returns a repaired JSON string if successful, or None if all fail.
    """
    # Attempt 1: Fix unquoted keys via regex
    try:
        repaired = re.sub(
            r'(?<=[{,])\s*(\w+)\s*:',
            r'"\1":',
            json_str,
        )
        json.loads(repaired)  # validate
        return repaired
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 2: Fix missing values (e.g. {"key": ,} -> {"key": null,})
    try:
        repaired = re.sub(r':\s*,', ': null,', json_str)
        repaired = re.sub(r':\s*}', ': null}', repaired)
        json.loads(repaired)
        return repaired
    except (json.JSONDecodeError, ValueError):
        pass

    # Attempt 3: Trim from the end until we get valid JSON
    try:
        for trim in range(1, min(50, len(json_str) // 4)):
            candidate = json_str[:-trim].rstrip()
            if candidate.endswith("}"):
                try:
                    json.loads(candidate)
                    return candidate
                except json.JSONDecodeError:
                    continue
    except (json.JSONDecodeError, ValueError):
        pass

    return None


def parse_json_with_retry(raw: str, max_retries: int = 1, repair: bool = True) -> dict | list:
    """Parse JSON from potentially messy LLM output, with optional repair.

    Args:
        raw: Raw LLM response text.
        max_retries: How many times to re-extract and re-parse (0 = single attempt).
        repair: If True, applies extract_json cleaning first.

    Returns:
        Parsed dict or list.

    Raises:
        json.JSONDecodeError: If parsing fails after all attempts.
    """
    if repair:
        cleaned = extract_json(raw)
    else:
        cleaned = raw.strip()

    # First attempt
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        if max_retries <= 0:
            # Try aggressive repair as last resort
            repaired = _try_repair_json(cleaned)
            if repaired:
                logger.info("JSON repaired successfully via _try_repair_json")
                return json.loads(repaired)
            raise
        logger.debug(f"JSON parse attempt 1 failed: {e}, trying repair...")

    # Retry with more aggressive cleaning
    for attempt in range(2, max_retries + 2):
        try:
            text = raw.strip()
            text = _INVISIBLE_CHARS_RE.sub("", text)
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end > start:
                candidate = text[start : end + 1]
                candidate = _CONTROL_CHARS_RE.sub("", candidate)
                candidate = _TRAILING_COMMA_RE.sub(r"\1", candidate)
                return json.loads(candidate)
        except json.JSONDecodeError:
            pass

        if attempt >= max_retries + 1:
            break

    # Final: try aggressive repair
    repaired = _try_repair_json(cleaned)
    if repaired:
        logger.info("JSON repaired successfully via _try_repair_json (final attempt)")
        return json.loads(repaired)

    raise json.JSONDecodeError(
        f"Failed to parse JSON after {max_retries + 1} attempts",
        doc=raw[:200],
        pos=0,
    )