"""Presentation-only localization; canonical IDs and domain records stay unchanged."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from importlib.resources import files

LANGUAGES = {"en": "English", "zh": "中文"}
_language = ContextVar("robodataops_language", default="en")
ENGLISH = json.loads(files("robodataops").joinpath("locales/en.json").read_text(encoding="utf-8"))
_TOKEN = re.compile(r"\{(\d+)\}")
_patterns = []
for source, target in ENGLISH.items():
    if _TOKEN.search(source):
        parts, cursor = [], 0
        indices = []
        for match in _TOKEN.finditer(source):
            parts.extend([re.escape(source[cursor : match.start()]), "(.+?)"])
            indices.append(int(match.group(1)))
            cursor = match.end()
        parts.append(re.escape(source[cursor:]))
        _patterns.append((re.compile("^" + "".join(parts) + "$", re.DOTALL), indices, target))


def set_language(language: str) -> None:
    if language not in LANGUAGES:
        raise ValueError("Unsupported language")
    _language.set(language)


def get_language() -> str:
    return _language.get()


def tr(value, *, language=None):
    """Translate known product copy; unknown source text is preserved verbatim."""
    if not isinstance(value, str) or (language or get_language()) == "zh":
        return value
    if value in ENGLISH:
        return ENGLISH[value]
    for pattern, indices, target in _patterns:
        match = pattern.fullmatch(value)
        if match:
            captures = dict(zip(indices, match.groups(), strict=True))
            return target.format(*(captures[i] for i in range(max(indices) + 1)))
    return value
