"""Canonical sensor-metric registry — the standardized measurement vocabulary.

Single source of truth for the numeric metrics a station can report: their
canonical unit, plausible physical bounds (for ingest validation), and a human
description. Datastreams store the resolved unit at creation, so historical data
stays self-describing even if this registry later changes.

Unknown numeric metrics are still accepted at ingest (stored on a datastream with
no unit and no range check), so a device can report a new field without a code
change; listing one here just makes it validated and self-describing.

Non-measurement device fields are deliberately NOT in this registry:
``firmwareVersion`` and ``wakeReason`` are stored as reading-envelope labels
rather than observations. See ``RESERVED_READING_KEYS``.
"""

from __future__ import annotations

from dataclasses import dataclass

# A station can hold several sensors of the same metric (e.g. indoor vs outdoor
# temperature); each is a separate datastream identified by this channel. Devices
# that don't disambiguate land on the default channel.
DEFAULT_CHANNEL = "default"

# Device payload keys that are recognised but are not measurements. The request
# model consumes them as fields (firmware/wake become envelope labels), so they
# never become observations.
RESERVED_READING_KEYS = frozenset({"firmwareVersion", "wakeReason"})


@dataclass(frozen=True)
class MetricSpec:
    """Canonical definition of one standardized metric."""

    unit: str
    minimum: float
    maximum: float
    description: str


# Canonical unit + plausible physical bounds per known metric. A reported value
# outside [minimum, maximum] is rejected at ingest as malformed. Units are stored
# canonically; conversion to a viewer's preferred unit happens at display time.
METRICS: dict[str, MetricSpec] = {
    "temperature": MetricSpec("degC", -90.0, 60.0, "Ambient air temperature."),
    "humidity": MetricSpec("percent", 0.0, 100.0, "Relative humidity."),
    "pressure": MetricSpec("hPa", 300.0, 1100.0, "Barometric pressure."),
    "battery": MetricSpec("percent", 0.0, 100.0, "Battery charge level."),
    "reception": MetricSpec("percent", 0.0, 100.0, "Cellular / network signal quality."),
    "voltage": MetricSpec("V", 0.0, 60.0, "Supply / battery voltage."),
    "deviceTemperature": MetricSpec("degC", -90.0, 150.0, "Internal device temperature."),
}


def metric_unit(metric: str) -> str | None:
    """Canonical unit for a known metric, or None for an unregistered one."""
    spec = METRICS.get(metric)
    return spec.unit if spec is not None else None
