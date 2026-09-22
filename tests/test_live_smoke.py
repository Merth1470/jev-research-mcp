"""Optional live JEV smoke test. Runs ONLY with TYPESAFE_API_KEY set.

Skipped in ordinary CI. Verifies the current API/SDK contract end to end:
small decision request -> expected response structure.
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("TYPESAFE_API_KEY"),
    reason="live JEV smoke test requires TYPESAFE_API_KEY",
)


async def test_live_jev_small_decision() -> None:
    from jev_evidence_mcp.jev.sdk_provider import SdkDecisionProvider

    provider = SdkDecisionProvider(api_key=os.environ["TYPESAFE_API_KEY"])
    result = await provider.decide_questions(
        state={
            "task": "Is the sky blue?",
            "candidates": [{"id": "r0", "text": "The sky is blue."}],
        },
        questions={
            "relevant__r0": {
                "type": "noul",
                "instructions": "Is this candidate relevant to the task?",
            }
        },
        meta={"relevant__r0": "relevant__r0"},
    )
    assert len(result.decisions) == 1
    assert 0.0 <= result.decisions[0].value <= 1.0
    assert result.model, "expected model name in live response"
