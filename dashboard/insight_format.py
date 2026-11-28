"""Display formatting for dashboard finding sentences."""

from __future__ import annotations


def add_selected_source(sentence: str, selected_sources: list[str]) -> str:
    """Append one source label when the dashboard has a single source filter."""
    if len(selected_sources) != 1:
        return sentence

    source = str(selected_sources[0]).strip()
    display_name = {"remotive": "Remotive", "jobicy": "Jobicy"}.get(
        source.casefold(), source
    )
    if not display_name:
        return sentence
    if sentence.endswith("."):
        return f"{sentence[:-1]}; Source: {display_name}."
    return f"{sentence}; Source: {display_name}."
