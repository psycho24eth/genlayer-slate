# lib/helpers.py
import json

def parse_json(raw: str) -> dict:
    """Strip markdown code fence if present and parse json."""
    text = raw.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return json.loads(text.strip())

def calculate_variance(values: list[float]) -> float:
    """Returns sample variance of validator scores."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((x - mean) ** 2 for x in values) / len(values)
