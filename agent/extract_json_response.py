import json
import re
from typing import Optional, Union

def extract_json(text: str) -> Optional[Union[dict, list]]:
    """
    Extract JSON from LLM response text.
    Handles: ```json ... ```, raw JSON, or JSON embedded in markdown.
    """
    if not text:
        return None

    # Strategy 1: ```json ... ``` block
    pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
    matches = re.findall(pattern, text)
    for match in matches:
        try:
            return json.loads(match.strip())
        except json.JSONDecodeError:
            continue

    # Strategy 2: Raw JSON object/array
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(text)):
            if text[i] == start_char:
                depth += 1
            elif text[i] == end_char:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start:i + 1])
                    except json.JSONDecodeError:
                        break
    return None
