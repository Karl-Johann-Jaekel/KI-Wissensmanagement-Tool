"""Retrieval evaluation against the demo notebook (read-only, no LLM call).

Measures each ranking list on its own and the fused result, so ADR-04 rests on numbers:

- hit@8: is at least one passage from the expected pages among the first eight?
- MRR@8: 1 / rank of the first such passage, 0 if none in the first eight
- vector distance of the best match, for answerable vs. unanswerable questions: could a threshold
  tell "not in the sources" apart before asking the model?

The expected pages were looked up in the stored chunks, not guessed: a heading such as
"Artikel 50" and the obligations below it can sit on two pages, and both count.

    docker compose cp backend/scripts/retrieval_eval.py backend:/tmp/eval.py
    docker compose exec backend python /tmp/eval.py
"""

import statistics
import sys
import uuid
from dataclasses import dataclass

sys.path.insert(0, "/app")

from sqlalchemy import select  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.db import get_sessionmaker  # noqa: E402
from app.deps import get_embedder  # noqa: E402
from app.models import Chunk, Notebook, Source  # noqa: E402
from app.retrieval.rrf import reciprocal_rank_fusion  # noqa: E402
from app.retrieval.search import reference_ranking, text_ranking, vector_ranking  # noqa: E402
from app.retrieval.text_query import extract_references  # noqa: E402

NOTEBOOK = "KI im Unternehmen: Recht & Verträge"
K = 8

KIVO, WKO, DSK, MVK = "KI-Verordnung", "Mustervertrag", "DSK", "EU-Mustervertrags"


@dataclass(frozen=True)
class Case:
    question: str
    source: str | None  # title prefix; None = the sources do not answer this
    pages: frozenset[int] = frozenset()


def case(question: str, source: str | None = None, *pages: int) -> Case:
    return Case(question, source, frozenset(pages))


CASES = [
    # with a legal reference in the question
    case("Was regelt Artikel 50 der KI-Verordnung?", KIVO, 122, 123),
    case("Welche Praktiken verbietet Artikel 5 der KI-Verordnung?", KIVO, 80, 81),
    case("Was verlangt Artikel 4 zur KI-Kompetenz?", KIVO, 80),
    # the same kind of content, asked in plain words
    case("Welche KI-Praktiken sind verboten?", KIVO, 80, 81),
    case("Nach welchen Regeln wird ein KI-System als hochriskant eingestuft?", KIVO, 84, 85),
    case("Welche Aufzeichnungspflichten gelten für Hochrisiko-KI-Systeme?", KIVO, 91, 92),
    case("Wie hoch sind die Geldbußen bei Verstößen gegen die KI-Verordnung?", KIVO, 168, 169),
    case("Ab wann gilt die KI-Verordnung?", KIVO, 71, 177, 178),
    case("Welche technisch-organisatorischen Maßnahmen sieht der Mustervertrag vor?", WKO, 7),
    case(
        "Was muss der Auftragsverarbeiter tun, bevor er einen weiteren "
        "Auftragsverarbeiter einsetzt?",
        WKO,
        5,
    ),
    case("Wie lange läuft die Vereinbarung zur Auftragsverarbeitung?", WKO, 3),
    case("Was gilt für Verarbeitungen in Drittstaaten?", WKO, 1),
    case("Was versteht die DSK unter Halluzinationen?", DSK, 9, 14),
    case("Wie werden personenbezogene Daten in einem RAG-System gelöscht?", DSK, 4, 13),
    case("Aus welchen Komponenten besteht ein RAG-System?", DSK, 6),
    case("Welche Rechte an Datensätzen regeln die Mustervertragsklauseln?", MVK, 6, 7, 8),
    case("Welches Auditrecht haben öffentliche Einrichtungen nach den MVK-KI?", MVK, 16),
    # not in the sources
    case("Wie hoch ist der gesetzliche Mindestlohn in Deutschland?"),
    case("Wer hat die Fußball-Weltmeisterschaft 2014 gewonnen?"),
    case("Welche Wirkstoffe enthält Ibuprofen?"),
    case("Wie funktioniert die Photosynthese bei Pflanzen?"),
    case("Wie hoch ist die Einkommensteuer für Selbstständige?"),
]

LISTS = ["Vektor", "Volltext", "Normverweis", "RRF (fusioniert)"]


def rank_of_first_hit(ranked: list[uuid.UUID], relevant: set[uuid.UUID]) -> int | None:
    for rank, chunk_id in enumerate(ranked[:K], start=1):
        if chunk_id in relevant:
            return rank
    return None


def main() -> None:
    settings = get_settings()
    embedder = get_embedder()
    with get_sessionmaker()() as db:
        notebook = db.scalar(select(Notebook).where(Notebook.title == NOTEBOOK))
        if notebook is None:
            sys.exit(f"Notebook {NOTEBOOK!r} nicht gefunden")

        scores: dict[str, list[float]] = {name: [] for name in LISTS}
        hits: dict[str, list[bool]] = {name: [] for name in LISTS}
        distances: dict[bool, list[float]] = {True: [], False: []}
        reference_questions = 0
        rows: list[str] = []

        for c in CASES:
            vector = embedder.embed_query(c.question)
            vector_ids = vector_ranking(
                db, notebook.id, None, vector, settings.retrieval_candidates
            )
            text_ids = text_ranking(
                db, notebook.id, None, c.question, settings.retrieval_candidates
            )
            reference_ids = reference_ranking(
                db, notebook.id, None, c.question, settings.retrieval_candidates
            )
            fused = reciprocal_rank_fusion(
                [vector_ids, text_ids, reference_ids], weights=[1.0, 1.0, 2.0], limit=K
            )

            best = db.scalar(
                select(Chunk.embedding.cosine_distance(vector))
                .join(Source, Source.id == Chunk.source_id)
                .where(Source.notebook_id == notebook.id)
                .order_by(Chunk.embedding.cosine_distance(vector))
                .limit(1)
            )
            distances[c.source is not None].append(float(best))

            if c.source is None:
                rows.append(f"| {c.question} | – | – | – | – | {best:.3f} |")
                continue

            relevant = set(
                db.scalars(
                    select(Chunk.id)
                    .join(Source, Source.id == Chunk.source_id)
                    .where(
                        Source.notebook_id == notebook.id,
                        Source.title.like(f"{c.source}%"),
                        Chunk.page.in_(c.pages),
                    )
                )
            )
            has_reference = bool(extract_references(c.question))
            reference_questions += has_reference
            cells = []
            for name, ranked in zip(
                LISTS, [vector_ids, text_ids, reference_ids, fused], strict=True
            ):
                if name == "Normverweis" and not has_reference:
                    cells.append("·")
                    continue
                rank = rank_of_first_hit(ranked, relevant)
                hits[name].append(rank is not None)
                scores[name].append(1 / rank if rank else 0.0)
                cells.append(str(rank) if rank else "✗")
            rows.append(f"| {c.question} | {' | '.join(cells)} | {best:.3f} |")

    print("## Rang des ersten relevanten Abschnitts (✗ = nicht unter den ersten acht)\n")
    print("| Frage | Vektor | Volltext | Normverweis | RRF | beste Distanz |")
    print("|---|---|---|---|---|---|")
    print("\n".join(rows))

    print("\n## Zusammenfassung\n")
    print("| Liste | Fragen | hit@8 | MRR@8 |")
    print("|---|---|---|---|")
    for name in LISTS:
        n = len(hits[name])
        rate = sum(hits[name]) / n
        mrr = statistics.fmean(scores[name])
        print(f"| {name} | {n} | {rate:.0%} | {mrr:.2f} |")

    print("\n## Vektor-Distanz des besten Treffers\n")
    print("| | Fragen | min | Median | max |")
    print("|---|---|---|---|---|")
    for answerable, label in [(True, "beantwortbar"), (False, "nicht beantwortbar")]:
        d = distances[answerable]
        print(f"| {label} | {len(d)} | {min(d):.3f} | {statistics.median(d):.3f} | {max(d):.3f} |")
    print(
        f"\nNormverweis-Liste bewertet nur die {reference_questions} Fragen mit Artikelnummer; "
        "ohne Verweis liefert sie absichtlich nichts."
    )


if __name__ == "__main__":
    main()
