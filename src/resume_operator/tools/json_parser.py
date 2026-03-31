"""Extract JSON from LLM responses that may include code fences or extra text."""

import json
import re
from typing import Any


def extract_json(text: str) -> dict[str, Any]:
    """Extract a JSON object from text that may contain surrounding content.

    Handles:
    - Raw JSON: ``{"key": "value"}``
    - Code-fenced: ``````json\\n{"key": "value"}\\n``````
    - Text-wrapped: ``Here is the result: {"key": "value"} Hope this helps!``

    Args:
        text: Raw text potentially containing a JSON object.

    Returns:
        Parsed JSON as a dict.

    Raises:
        ValueError: If no valid JSON object can be extracted.
    """
    stripped = text.strip()

    # 1. Try direct parse
    try:
        result = json.loads(stripped)
        if isinstance(result, dict):
            return result
    except json.JSONDecodeError:
        pass

    # 2. Try stripping markdown code fences
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", stripped, re.DOTALL)
    if fence_match:
        try:
            result = json.loads(fence_match.group(1).strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

    # 3. Try extracting the first {...} block via brace matching
    start = stripped.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(stripped)):
            if stripped[i] == "{":
                depth += 1
            elif stripped[i] == "}":
                depth -= 1
                if depth == 0:
                    candidate = stripped[start : i + 1]
                    try:
                        result = json.loads(candidate)
                        if isinstance(result, dict):
                            return result
                    except json.JSONDecodeError:
                        pass
                    break

    msg = f"No valid JSON object found in text: {stripped[:100]}"
    raise ValueError(msg)
