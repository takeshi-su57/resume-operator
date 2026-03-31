"""Tests for the JSON extraction utility."""

import pytest

from resume_operator.tools.json_parser import extract_json


class TestExtractJson:
    def test_raw_json(self) -> None:
        text = '{"name": "Jane", "score": 0.85}'
        result = extract_json(text)
        assert result["name"] == "Jane"
        assert result["score"] == 0.85

    def test_json_with_whitespace(self) -> None:
        text = '  \n  {"key": "value"}  \n  '
        result = extract_json(text)
        assert result["key"] == "value"

    def test_code_fenced_json(self) -> None:
        text = '```json\n{"name": "Jane", "skills": ["Python"]}\n```'
        result = extract_json(text)
        assert result["name"] == "Jane"
        assert result["skills"] == ["Python"]

    def test_code_fenced_without_language(self) -> None:
        text = '```\n{"key": "value"}\n```'
        result = extract_json(text)
        assert result["key"] == "value"

    def test_text_wrapped_json(self) -> None:
        text = 'Here is the result:\n{"score": 0.72, "reasoning": "Good match"}\nHope this helps!'
        result = extract_json(text)
        assert result["score"] == 0.72
        assert result["reasoning"] == "Good match"

    def test_nested_objects(self) -> None:
        text = '{"outer": {"inner": "value"}, "list": [1, 2, 3]}'
        result = extract_json(text)
        assert result["outer"]["inner"] == "value"
        assert result["list"] == [1, 2, 3]

    def test_text_before_code_fence(self) -> None:
        text = (
            'Sure! Here is the JSON:\n```json\n{"key": "value"}\n```\nLet me know if you need more.'
        )
        result = extract_json(text)
        assert result["key"] == "value"

    def test_raises_on_invalid_json(self) -> None:
        with pytest.raises(ValueError, match="No valid JSON"):
            extract_json("this is not json at all")

    def test_raises_on_empty_string(self) -> None:
        with pytest.raises(ValueError, match="No valid JSON"):
            extract_json("")

    def test_raises_on_json_array(self) -> None:
        """Only dicts are accepted, not arrays."""
        with pytest.raises(ValueError, match="No valid JSON"):
            extract_json("[1, 2, 3]")

    def test_json_with_braces_in_strings(self) -> None:
        text = '{"template": "Use {placeholder} here", "count": 1}'
        result = extract_json(text)
        assert result["template"] == "Use {placeholder} here"
        assert result["count"] == 1
