"""Explicit Streamlit rendering adapter: localize views, retain widget values.

This is not a global monkey patch. Each session uses its own context language.
Selectors return canonical option IDs, and downloads/JSON audit records remain raw.
"""

from functools import wraps
from hashlib import sha256

import pandas as pd
import streamlit

from robodataops.i18n import get_language, tr

_LABELS = {
    "title",
    "header",
    "subheader",
    "caption",
    "markdown",
    "text",
    "info",
    "warning",
    "error",
    "success",
    "spinner",
    "expander",
    "button",
    "download_button",
    "form_submit_button",
    "text_input",
    "text_area",
    "number_input",
    "checkbox",
    "file_uploader",
    "metric",
    "TextColumn",
    "NumberColumn",
    "SelectboxColumn",
}
_SELECTORS = {"selectbox", "radio", "multiselect"}
_STATEFUL = _SELECTORS | {"text_input", "text_area", "number_input", "checkbox", "file_uploader"}


def localized_frame(frame):
    result = frame.copy(deep=True)
    for column in result.columns:
        if result[column].dtype == object or pd.api.types.is_string_dtype(result[column]):
            result[column] = result[column].map(tr)
    return result.rename(columns=tr)


class LocalizedUI:
    def __init__(self, raw, scope="root"):
        self.raw = raw
        self.scope = scope

    def __enter__(self):
        self.raw.__enter__()
        return self

    def __exit__(self, *args):
        return self.raw.__exit__(*args)

    def __getattr__(self, name):
        function = getattr(self.raw, name)
        if name in {"sidebar", "column_config"}:
            return LocalizedUI(function, self.scope + "/" + name)
        if not callable(function):
            return function

        @wraps(function)
        def render(*args, **kwargs):
            args = list(args)
            original_label = args[0] if args else kwargs.get("label", "")
            if name in _STATEFUL and "key" not in kwargs:
                identity = f"{self.scope}/{name}/{original_label}"
                kwargs["key"] = "localized-" + sha256(identity.encode()).hexdigest()[:20]
            if name in _LABELS | _SELECTORS and args:
                args[0] = tr(args[0])
            if name == "metric" and len(args) > 1:
                args[1] = tr(args[1])
            if name in _SELECTORS:
                formatter = kwargs.get("format_func", str)
                language = get_language()
                kwargs["format_func"] = lambda value: tr(formatter(value), language=language)
            for key in ("label", "help", "placeholder", "alt"):
                if key in kwargs:
                    kwargs[key] = tr(kwargs[key])
            if name in {"dataframe", "bar_chart"} and args and isinstance(args[0], pd.DataFrame):
                args[0] = localized_frame(args[0])
            if name == "json" and args:
                # JSON is raw provenance, deliberately not translated.
                pass
            if name == "data_editor" and args:
                args[0] = args[0].copy(deep=True)
                if "task" in args[0].columns:
                    args[0]["task"] = args[0]["task"].map(tr)
            if name == "set_page_config" and "page_title" in kwargs:
                kwargs["page_title"] = tr(kwargs["page_title"])
            value = function(*args, **kwargs)
            if name == "columns":
                return [
                    LocalizedUI(column, f"{self.scope}/column-{index}")
                    for index, column in enumerate(value)
                ]
            if name in {"form", "expander", "spinner"}:
                return LocalizedUI(value, f"{self.scope}/{name}/{original_label}")
            return value

        return render


st = LocalizedUI(streamlit)
