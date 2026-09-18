"""Words for languages beyond the two this was written in.

The glossary in descriptions.py holds Swedish and English, the languages the
pump was read and the texts verified in. A third language is added here instead
of moving every entry: English source text on the left, the translation on the
right. What is missing falls back to English, which reads as a whole sentence
in the wrong language rather than as a half-translated one.

`LANGUAGES` is what the integration claims to speak. Adding German means
filling in TEXTS["de"] and the same keys in translations/de.json; nothing else
in the integration has to change.
"""

from __future__ import annotations

#: The languages names and explanations are written in. The order is only for
#: reading; Swedish and English are complete, the rest fall back to English.
LANGUAGES = ("sv", "en", "de", "fr")

#: English source text -> translation. Empty until someone who speaks the
#: language fills it in; an empty table simply leaves the page in English.
TEXTS: dict[str, dict[str, str]] = {
    "de": {},
    "fr": {},
}


def normalize(language: str | None) -> str:
    """A Home Assistant language ("sv", "de-DE", "en_GB") as a plain code."""
    return str(language or "").replace("_", "-").split("-")[0].lower()


def translate(text: str, language: str | None) -> str:
    """`text`, which is English, in `language` if that is known here."""
    return TEXTS.get(normalize(language), {}).get(text, text)


def entity_language(system: str | None, stored: str | None = None) -> str:
    """Which language the entities and the NIBE page speak.

    Home Assistant's own language, so that names, explanations and headings are
    never in different ones - the complaint that prompted this. The language
    stored when the pump was added is only a fallback, for an installation that
    has not set one, and anything unknown becomes English.
    """
    for candidate in (system, stored):
        code = normalize(candidate)
        if code in LANGUAGES:
            return code
    return "en"
