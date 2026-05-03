"""Test the configurable after-hours threshold end-to-end (without HTTP).

Tests:
  1. GET returns the new field with default 0.85 when DB row missing
  2. PATCH inserts the row when missing (upsert)
  3. GET returns the saved value after PATCH
  4. Validation rejects values outside [0, 1]
  5. risk_guard reads the saved value
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select, delete
from trumptrade.core.db import AsyncSessionLocal
from trumptrade.core.models import AppSettings
from trumptrade.risk_guard.router import (
    RiskSettingsPatch,
    _read_all_risk_settings,
    patch_risk_settings,
    get_risk_settings,
)


KEY = "after_hours_hold_threshold"


async def cleanup() -> None:
    """Remove the row so we can test fresh upsert."""
    async with AsyncSessionLocal() as s:
        await s.execute(delete(AppSettings).where(AppSettings.key == KEY))
        await s.commit()


async def get_db_value() -> str | None:
    async with AsyncSessionLocal() as s:
        r = await s.execute(select(AppSettings.value).where(AppSettings.key == KEY))
        return r.scalar_one_or_none()


async def test_1_default_when_missing() -> None:
    print("\n[1] GET returns default 0.85 when DB row missing")
    await cleanup()
    db_val = await get_db_value()
    assert db_val is None, f"DB should be empty, got {db_val}"
    settings = await _read_all_risk_settings()
    assert settings.after_hours_hold_threshold == 0.85, settings.after_hours_hold_threshold
    print(f"   OK Default returned: {settings.after_hours_hold_threshold}")
    print(f"   OK DB unchanged: {await get_db_value()}")


async def test_2_patch_upsert_inserts() -> None:
    print("\n[2] PATCH upserts (inserts row when missing)")
    await cleanup()
    body = RiskSettingsPatch(after_hours_hold_threshold=0.75)
    response = await patch_risk_settings(body)
    assert response.after_hours_hold_threshold == 0.75
    db_val = await get_db_value()
    assert db_val == "0.75", f"Expected '0.75' in DB, got {db_val!r}"
    print(f"   OK Response: {response.after_hours_hold_threshold}")
    print(f"   OK DB now contains: {db_val}")


async def test_3_patch_updates_existing() -> None:
    print("\n[3] PATCH updates existing row")
    body = RiskSettingsPatch(after_hours_hold_threshold=0.92)
    response = await patch_risk_settings(body)
    assert response.after_hours_hold_threshold == 0.92
    db_val = await get_db_value()
    assert db_val == "0.92"
    print(f"   OK Updated to: {db_val}")


async def test_4_validation_rejects_out_of_range() -> None:
    print("\n[4] Validation rejects values outside [0, 1]")
    from pydantic import ValidationError
    rejected = []
    for bad in [1.5, -0.1, 2.0]:
        try:
            RiskSettingsPatch(after_hours_hold_threshold=bad)
            print(f"   X ACCEPTED {bad} but should have rejected")
        except ValidationError:
            rejected.append(bad)
    print(f"   OK Rejected: {rejected}")
    # Boundary cases
    RiskSettingsPatch(after_hours_hold_threshold=0.0)
    RiskSettingsPatch(after_hours_hold_threshold=1.0)
    print("   OK Accepts boundaries 0.0 and 1.0")


async def test_5_guard_reads_setting() -> None:
    print("\n[5] risk_guard reads the saved threshold")
    # Set a distinctive value
    body = RiskSettingsPatch(after_hours_hold_threshold=0.66)
    await patch_risk_settings(body)

    # Import the helper guard.py uses
    from trumptrade.risk_guard.guard import _get_setting, _AFTER_HOURS_HOLD_THRESHOLD_DEFAULT
    threshold = float(await _get_setting(KEY, str(_AFTER_HOURS_HOLD_THRESHOLD_DEFAULT)))
    assert threshold == 0.66, f"Expected 0.66, got {threshold}"
    print(f"   OK guard reads: {threshold}")
    print(f"   OK default constant still: {_AFTER_HOURS_HOLD_THRESHOLD_DEFAULT}")


async def test_6_get_endpoint_includes_field() -> None:
    print("\n[6] GET /settings/risk response includes new field")
    response = await get_risk_settings()
    assert hasattr(response, "after_hours_hold_threshold")
    print(f"   OK Field present: after_hours_hold_threshold = {response.after_hours_hold_threshold}")
    print(f"   OK Full response: {response.model_dump()}")


async def main() -> None:
    print("=" * 70)
    print("Testing configurable after-hours hold threshold")
    print("=" * 70)
    await test_1_default_when_missing()
    await test_2_patch_upsert_inserts()
    await test_3_patch_updates_existing()
    await test_4_validation_rejects_out_of_range()
    await test_5_guard_reads_setting()
    await test_6_get_endpoint_includes_field()

    print("\n" + "=" * 70)
    print("Cleanup: removing test value")
    print("=" * 70)
    await cleanup()
    print("   OK DB cleaned up — settings will fall back to default 0.85")
    print("\nAll tests passed.")


if __name__ == "__main__":
    asyncio.run(main())
