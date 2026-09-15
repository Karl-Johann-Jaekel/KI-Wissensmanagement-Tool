import pytest

from app.ingest.guide import MAX_GROUPS, build_guide, group_chunks, parse_guide
from app.llm.provider import LLMError
from tests.fakes import FakeLLM


def test_short_source_needs_a_single_call() -> None:
    llm = FakeLLM()
    guide = build_guide(llm, "Titel", ["Inhalt eins.", "Inhalt zwei."])
    assert guide.summary
    assert len(llm.calls) == 1
    assert llm.calls[0][1] is True  # json_mode


def test_long_source_uses_map_reduce() -> None:
    llm = FakeLLM(answer="Abschnittszusammenfassung.")
    chunks = ["x" * 1800] * 39  # 13 chunks fit into 24k chars → 3 groups
    build_guide(llm, "Titel", chunks)
    map_calls = [c for c in llm.calls if not c[1]]
    assert len(map_calls) == len(group_chunks(chunks)) == 3
    assert llm.calls[-1][1] is True
    assert "Zusammenfassungen der Abschnitte" in llm.calls[-1][0][1]["content"]


def test_grouping_is_capped() -> None:
    groups = group_chunks(["y" * 1000] * 1000)
    assert len(groups) <= MAX_GROUPS + 1
    assert sum(len(g) for g in groups) == 1000


def test_parse_guide_tolerates_code_fences_and_trims_lists() -> None:
    raw = (
        '```json\n{"summary": "S", "key_topics": ["a", " ", "b"], "suggested_questions": "x"}\n```'
    )
    guide = parse_guide(raw)
    assert guide.key_topics == ["a", "b"]
    assert guide.suggested_questions == []


def test_parse_guide_rejects_garbage() -> None:
    with pytest.raises(LLMError):
        parse_guide("Hier ist dein Guide: ...")
