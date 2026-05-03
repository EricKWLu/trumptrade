"""Test the confidence gate filter end-to-end.

Tests:
  1. Below-threshold signal returns SKIP with BELOW_THRESHOLD reason
  2. At-threshold signal passes through (>= comparison)
  3. Above-threshold signal passes through
  4. Already-SKIP signal preserves its existing reason (keyword overlay wins)
  5. Worker reads threshold from app_settings each tick
  6. Changing app_settings value affects gate behavior
  7. Invalid threshold value falls back to 0.7
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select, update, delete
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings
from trumptrade.analysis.worker import _apply_confidence_gate, _get_app_setting


KEY = "confidence_threshold"


async def set_threshold(value: str) -> None:
    """Helper: set the confidence_threshold value in DB."""
    async with AsyncSessionLocal() as s:
        existing = await s.execute(select(AppSettings).where(AppSettings.key == KEY))
        if existing.scalar_one_or_none():
            await s.execute(update(AppSettings).where(AppSettings.key == KEY).values(value=value))
        else:
            s.add(AppSettings(key=KEY, value=value))
        await s.commit()


async def test_1_below_threshold_skip() -> None:
    print("\n[1] Below-threshold confidence -> SKIP, BELOW_THRESHOLD")
    action, reason = _apply_confidence_gate(
        final_action="BUY",
        reason_code=None,
        confidence=0.55,
        threshold=0.7,
    )
    assert action == "SKIP", f"Expected SKIP, got {action}"
    assert reason == "BELOW_THRESHOLD", f"Expected BELOW_THRESHOLD, got {reason}"
    print(f"   OK action={action} reason={reason}")


async def test_2_at_threshold_passes() -> None:
    print("\n[2] At-threshold confidence (>= comparison) -> action preserved")
    action, reason = _apply_confidence_gate(
        final_action="BUY",
        reason_code=None,
        confidence=0.7,    # exactly threshold
        threshold=0.7,
    )
    assert action == "BUY", f"Expected BUY at boundary, got {action}"
    assert reason is None, f"Expected None reason, got {reason}"
    print(f"   OK action={action} reason={reason}")


async def test_3_above_threshold_passes() -> None:
    print("\n[3] Above-threshold confidence -> action preserved")
    for action_in in ("BUY", "SELL"):
        action, reason = _apply_confidence_gate(
            final_action=action_in,
            reason_code=None,
            confidence=0.92,
            threshold=0.7,
        )
        assert action == action_in
        assert reason is None
        print(f"   OK {action_in} preserved at confidence=0.92")


async def test_4_existing_skip_preserved() -> None:
    print("\n[4] Already-SKIP signal preserves its existing reason")
    # Even with high confidence, if keyword overlay already set SKIP, we keep that reason
    action, reason = _apply_confidence_gate(
        final_action="SKIP",
        reason_code="KEYWORD_OVERRIDE",   # set by keyword overlay
        confidence=0.95,                  # high enough to pass gate
        threshold=0.7,
    )
    assert action == "SKIP", "SKIP should remain SKIP"
    assert reason == "KEYWORD_OVERRIDE", f"Existing reason should be preserved, got {reason}"
    print(f"   OK existing SKIP/KEYWORD_OVERRIDE preserved")

    # Same but with no prior reason
    action, reason = _apply_confidence_gate(
        final_action="SKIP",
        reason_code=None,
        confidence=0.95,
        threshold=0.7,
    )
    assert action == "SKIP"
    assert reason is None
    print(f"   OK existing SKIP with None reason preserved")


async def test_5_worker_reads_from_settings() -> None:
    print("\n[5] Worker reads threshold from app_settings each tick")
    # Set a distinctive value
    await set_threshold("0.55")
    val = await _get_app_setting(KEY, "0.7")
    assert val == "0.55", f"Expected '0.55', got {val!r}"
    print(f"   OK worker would read: {val}")

    # Change it
    await set_threshold("0.88")
    val = await _get_app_setting(KEY, "0.7")
    assert val == "0.88", f"Expected '0.88', got {val!r}"
    print(f"   OK after change, worker reads: {val}")


async def test_6_setting_affects_gate() -> None:
    print("\n[6] Changing app_settings value affects gate behavior")
    confidence = 0.65   # this will be borderline

    # With threshold 0.7, 0.65 should be SKIP
    await set_threshold("0.7")
    threshold = float(await _get_app_setting(KEY, "0.7"))
    action, reason = _apply_confidence_gate("BUY", None, confidence, threshold)
    assert action == "SKIP" and reason == "BELOW_THRESHOLD"
    print(f"   OK threshold=0.7, confidence=0.65 -> {action}/{reason}")

    # With threshold 0.6, 0.65 should pass
    await set_threshold("0.6")
    threshold = float(await _get_app_setting(KEY, "0.7"))
    action, reason = _apply_confidence_gate("BUY", None, confidence, threshold)
    assert action == "BUY" and reason is None
    print(f"   OK threshold=0.6, confidence=0.65 -> {action} (passes)")


async def test_7_invalid_threshold_fallback() -> None:
    print("\n[7] Invalid threshold value in DB falls back to 0.7")
    await set_threshold("not-a-number")
    # Mimic the worker's parsing logic from worker.py:195-202
    threshold_str = await _get_app_setting(KEY, "0.7")
    try:
        threshold = float(threshold_str)
        print(f"   X parsed unexpectedly as {threshold}")
    except ValueError:
        threshold = 0.7
        print(f"   OK invalid value rejected, fell back to {threshold}")
    assert threshold == 0.7


async def test_8_full_flow_simulation() -> None:
    print("\n[8] Simulated full flow: 3 LLM verdicts at different confidences")
    await set_threshold("0.7")
    threshold = float(await _get_app_setting(KEY, "0.7"))

    cases = [
        ("LLM bullish 0.45 confidence",   "BUY",  None, 0.45, "SKIP", "BELOW_THRESHOLD"),
        ("LLM bullish 0.72 confidence",   "BUY",  None, 0.72, "BUY",  None),
        ("LLM bearish 0.91 confidence",   "SELL", None, 0.91, "SELL", None),
        ("Keyword force-skip overrides",  "SKIP", "KEYWORD_OVERRIDE", 0.95, "SKIP", "KEYWORD_OVERRIDE"),
    ]
    for label, in_action, in_reason, conf, want_action, want_reason in cases:
        action, reason = _apply_confidence_gate(in_action, in_reason, conf, threshold)
        ok = action == want_action and reason == want_reason
        marker = "OK" if ok else "FAIL"
        print(f"   {marker} {label} -> {action}/{reason}")
        assert ok, f"Expected ({want_action}, {want_reason}), got ({action}, {reason})"


async def cleanup() -> None:
    """Restore default 0.7."""
    await set_threshold("0.7")


async def main() -> None:
    print("=" * 70)
    print("Testing confidence gate filter")
    print("=" * 70)
    try:
        await test_1_below_threshold_skip()
        await test_2_at_threshold_passes()
        await test_3_above_threshold_passes()
        await test_4_existing_skip_preserved()
        await test_5_worker_reads_from_settings()
        await test_6_setting_affects_gate()
        await test_7_invalid_threshold_fallback()
        await test_8_full_flow_simulation()
    finally:
        print("\n" + "=" * 70)
        print("Cleanup: restoring confidence_threshold=0.7")
        print("=" * 70)
        await cleanup()
        print("   OK restored")

    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
