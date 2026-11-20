import re

PATTERNS = [
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]{4}){2,7}(?: ?[A-Z0-9]{1,3})?\b")),
    ("EMAIL", re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")),
    ("TEL", re.compile(r"(?:\+|\b00)\d(?:[ .-]?\d){7,13}")),
]


def mask(text: str) -> tuple[str, dict]:
    mapping: dict[str, str] = {}
    for label, pattern in PATTERNS:

        def replace(match, label=label):
            value = match.group()
            for token, known in mapping.items():
                if known == value:
                    return token
            rank = sum(t.startswith("[" + label) for t in mapping) + 1
            token = f"[{label}_{rank}]"
            mapping[token] = value
            return token

        text = pattern.sub(replace, text)
    return text, mapping


def unmask(value, mapping: dict):
    if isinstance(value, str):
        for token, original in mapping.items():
            value = value.replace(token, original)
        return value
    if isinstance(value, dict):
        return {k: unmask(v, mapping) for k, v in value.items()}
    if isinstance(value, list):
        return [unmask(v, mapping) for v in value]
    return value