"""Build an OR tsquery and detect legal references in a natural-language question (ADR-04)."""

import re
from dataclasses import dataclass

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


# "Artikel 50", "Art. 5", "§ 42a", "Anhang III", "Article 12" – numbers matter here, and neither
# embeddings nor an OR full-text query rank them well.
_KINDS = {
    "artikel": r"(?:Artikel|Art\.|Article)",
    "art.": r"(?:Artikel|Art\.|Article)",
    "article": r"(?:Artikel|Art\.|Article)",
    "§": r"(?:§|Paragraph)",
    "paragraph": r"(?:§|Paragraph)",
    "anhang": r"(?:Anhang|Annex)",
    "annex": r"(?:Anhang|Annex)",
}
_REFERENCE_IN_QUESTION = re.compile(
    r"(Artikel|Art\.|Article|§|Paragraph|Anhang|Annex)\s*(\d{1,3}[a-z]?|[IVX]{1,5})(?![\w])",
    re.IGNORECASE,
)
# After a heading like "Artikel 50" comes its title ("Transparenzpflichten …"); a cross-reference
# continues with "Absatz", a lower-case word or punctuation.
_NOT_A_TITLE = r"(?:Abs|Absatz|Unterabsatz|UAbs|Buchstabe|Nummer|Nr|Satz|Paragraph)\b"


@dataclass(frozen=True)
class Reference:
    label: str
    sql_pattern: str  # PostgreSQL ARE, used with ~* (case-insensitive)
    heading: re.Pattern[str]


def extract_references(question: str) -> list[Reference]:
    references: list[Reference] = []
    for kind, number in _REFERENCE_IN_QUESTION.findall(question):
        kind_pattern = _KINDS[kind.lower()]
        if number.isalpha() and kind_pattern != _KINDS["anhang"]:
            continue  # roman numerals only for annexes ("Art. I" is not a reference)
        num = re.escape(number)
        label = f"{kind} {number}"
        if any(r.label.lower() == label.lower() for r in references):
            continue
        references.append(
            Reference(
                label=label,
                sql_pattern=rf"{kind_pattern}\s*{num}([^0-9a-z]|$)",
                heading=re.compile(
                    rf"(?i:{kind_pattern})\s*(?i:{num})\s+(?!{_NOT_A_TITLE})[A-ZÄÖÜ]"
                ),
            )
        )
    return references
