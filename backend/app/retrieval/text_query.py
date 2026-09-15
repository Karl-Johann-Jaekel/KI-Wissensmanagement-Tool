"""Build an OR tsquery from a natural-language question (ADR-04)."""

import re

# Short DE/EN list: the `simple` text search config has no stopword removal, and with OR
# semantics a single "die"/"the" would otherwise match nearly every chunk.
_STOPWORD_TEXT = """
    aber alle allem allen aller alles als also am an ander andere anderen anders auch auf aus bei
    bin bis bist da damit dann das dass dein deine dem den der des dessen dich die dies diese
    diesem diesen dieser dieses dir doch dort du durch ein eine einem einen einer eines er es
    etwas euch euer für gegen gibt hab habe haben hat hatte hätte hier hin ich ihm ihn ihnen ihr
    ihre im in ist ja jede jedem jeden jeder jedes jetzt kann kein keine können machen man mehr
    mein mich mir mit muss nach nicht nichts noch nun nur ob oder ohne sehr sein seine sich sie
    sind so solche soll sollte sondern sonst über um und uns unser unter viel vom von vor war
    waren warum was weil welche welchem welchen welcher welches wenn wer werden wie wieder wir
    wird wo wurde wurden zu zum zur zwischen erkläre beschreibe nenne fasse geht bitte
    a about all also an and any are as at be been but by can could did do does for from had has
    have how i if in into is it its me more most my no not of on or our she so some such than
    that the their them then there these they this those to was we were what when where which
    who why will with would you your explain describe tell please
"""
STOPWORDS = frozenset(_STOPWORD_TEXT.split())  # noqa: SIM905 - a word list reads better as text
MAX_TERMS = 24


def build_or_tsquery(question: str) -> str | None:
    terms: list[str] = []
    for token in re.findall(r"\w+", question.lower()):
        token = token.strip("_")
        if not token or token in STOPWORDS:
            continue
        if len(token) < 2 and not token.isdigit():
            continue
        if token not in terms:
            terms.append(token)
    if not terms:
        return None
    # tokens are \w-only, so they cannot inject tsquery operators
    return " | ".join(terms[:MAX_TERMS])
