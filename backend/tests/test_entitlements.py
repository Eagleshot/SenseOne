"""Tests for the entitlements seam (entitlements.py)."""

from entitlements import DEFAULT_PLAN, PLANS, Limits, limits_for, plan_for
from user_db import User


def _user(plan: str) -> User:
    return User(email="o@example.com", is_admin=False, created_at="", owner_id="o", plan=plan)


class TestPlanFor:
    def test_anonymous_is_default(self):
        assert plan_for(None) == DEFAULT_PLAN == "free"

    def test_known_plan_passthrough(self):
        assert plan_for(_user("pro")) == "pro"
        assert plan_for(_user("business")) == "business"

    def test_unknown_plan_falls_back_to_default(self):
        assert plan_for(_user("enterprise-typo")) == "free"


class TestLimitsFor:
    def test_default_user_gets_free_limits(self):
        # A freshly created user defaults to the free plan.
        assert limits_for(_user("free")) is PLANS["free"]
        assert limits_for(None) is PLANS["free"]

    def test_pro_and_business_lookup(self):
        assert limits_for(_user("pro")) is PLANS["pro"]
        assert limits_for(_user("business")) is PLANS["business"]

    def test_free_has_included_station_cap_paid_is_unlimited(self):
        assert limits_for(_user("free")).included_station_count == 3
        assert limits_for(_user("pro")).included_station_count is None
        assert limits_for(_user("business")).included_station_count is None

    def test_limits_are_frozen(self):
        # Limits is an immutable value object; callers can't mutate the shared plan.
        import dataclasses

        import pytest

        with pytest.raises(dataclasses.FrozenInstanceError):
            limits_for(_user("free")).max_image_width = 9999  # type: ignore[misc]

    def test_resolution_ladder_increases_with_tier(self):
        free, pro, business = (limits_for(_user(p)) for p in ("free", "pro", "business"))
        assert free.max_image_width < pro.max_image_width < business.max_image_width
        assert isinstance(business, Limits)
