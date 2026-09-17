"""Parsing and embedding hold a whole document in memory: uploads must not run side by side.

The 200-page AI Act alone peaked at 1.95 GiB on the VPS. Two such uploads in parallel would
exceed the backend's memory limit and get the process killed.
"""

import threading
import time
import uuid

import pytest

from app.db import get_sessionmaker
from app.ingest import pipeline
from app.ingest.chunker import Segment
from app.ingest.parsers import ParsedDocument
from app.models import Notebook, Source
from tests.fakes import FakeEmbedder, FakeLLM


def _processing_sources(count: int) -> list[uuid.UUID]:
    with get_sessionmaker()() as db:
        notebook = Notebook(title="Parallele Uploads")
        db.add(notebook)
        db.flush()
        sources = [
            Source(notebook_id=notebook.id, title=f"quelle-{i}", type="text", origin=f"q{i}.txt")
            for i in range(count)
        ]
        db.add_all(sources)
        db.commit()
        return [source.id for source in sources]


def _peak_parallel_loads(count: int) -> tuple[int, list[uuid.UUID]]:
    """Start `count` ingestions at once; report how many were inside `load` together."""
    active = peak = 0
    lock = threading.Lock()

    def slow_load() -> ParsedDocument:
        nonlocal active, peak
        with lock:
            active += 1
            peak = max(peak, active)
        time.sleep(0.3)
        with lock:
            active -= 1
        return ParsedDocument(
            title="Dokument", segments=[Segment(text="Photosynthese braucht Licht.")]
        )

    source_ids = _processing_sources(count)
    threads = [
        threading.Thread(
            target=pipeline.ingest_source, args=(source_id, slow_load, FakeEmbedder(), FakeLLM())
        )
        for source_id in source_ids
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return peak, source_ids


def test_uploads_are_parsed_and_embedded_one_at_a_time() -> None:
    pipeline._ingest_slots.cache_clear()
    peak, _ = _peak_parallel_loads(3)
    assert peak == 1


def test_the_limit_is_what_keeps_them_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control: with room for two, two do overlap — so the test above can fail."""
    two = threading.BoundedSemaphore(2)
    monkeypatch.setattr(pipeline, "_ingest_slots", lambda: two)
    peak, _ = _peak_parallel_loads(3)
    assert peak == 2


def test_queued_uploads_finish_once_a_slot_frees_up() -> None:
    pipeline._ingest_slots.cache_clear()
    _, source_ids = _peak_parallel_loads(3)

    with get_sessionmaker()() as db:
        statuses = [db.get(Source, source_id).status for source_id in source_ids]  # type: ignore[union-attr]
    assert statuses == ["ready", "ready", "ready"]
