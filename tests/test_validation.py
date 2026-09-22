"""JEV response validation: untrusted input checked strictly."""

from __future__ import annotations

import pytest

from jev_evidence_mcp.errors import ErrorCode, EvidenceError
from jev_evidence_mcp.jev.validation import validate_decisions

EXPECTED = {"relevant__r0", "useful__r0"}
META = {"relevant__r0": "relevant__r0", "useful__r0": "useful__r0"}


def test_valid_answers_pass() -> None:
    result = validate_decisions(
        expected_question_ids=EXPECTED,
        meta=META,
        raw_answers={"relevant__r0": 0.9, "useful__r0": 0.2},
    )
    assert {d.candidate_id for d in result.decisions} == {"r0"}
    assert result.by_candidate("r0") == {"relevant": 0.9, "useful": 0.2}


def test_answer_objects_with_noul_field_accepted() -> None:
    result = validate_decisions(
        expected_question_ids=EXPECTED,
        meta=META,
        raw_answers={"relevant__r0": {"type": "noul", "noul": 0.7}, "useful__r0": {"noul": 0.6}},
    )
    assert result.by_candidate("r0")["relevant"] == 0.7


def test_missing_answer_rejected() -> None:
    with pytest.raises(EvidenceError) as exc_info:
        validate_decisions(
            expected_question_ids=EXPECTED, meta=META, raw_answers={"relevant__r0": 0.9}
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


def test_unexpected_id_rejected() -> None:
    with pytest.raises(EvidenceError) as exc_info:
        validate_decisions(
            expected_question_ids=EXPECTED,
            meta={**META, "evil__r9": "evil__r9"},
            raw_answers={"relevant__r0": 0.9, "useful__r0": 0.1, "evil__r9": 1.0},
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


def test_duplicate_id_rejected() -> None:
    with pytest.raises(EvidenceError) as exc_info:
        validate_decisions(
            expected_question_ids=EXPECTED,
            meta=META,
            raw_answers=[
                ("relevant__r0", 0.9),
                ("relevant__r0", 0.1),
                ("useful__r0", 0.5),
            ],
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR


@pytest.mark.parametrize("bad", [-0.1, 1.5, 2.0, float("nan"), "yes", True, None])
def test_out_of_range_or_nonnumeric_rejected(bad: object) -> None:
    with pytest.raises(EvidenceError) as exc_info:
        validate_decisions(
            expected_question_ids=EXPECTED,
            meta=META,
            raw_answers={"relevant__r0": bad, "useful__r0": 0.5},
        )
    assert exc_info.value.code == ErrorCode.VALIDATION_ERROR
