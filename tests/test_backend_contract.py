"""Every field the report builds must survive the trip to stats.rnet.se.

v1.3.0 shipped three fields that never arrived intact, and nothing noticed:

* `product_code` 65443 was stored as 9999, because the backend's range is sized
  for CTC's four-digit codes and clamps anything larger without an error;
* `block_reads` and `scan_interval_s` were dropped, because metrics are a
  closed list of physical quantities on the backend;
* `firmwares` never left the house, because the shared stats.py passed only a
  singular `firmware` key through at the time.

The backend's rules below are copied from its lib/ingest.ts; if it changes,
change them here too. stats.py's list is read from the file itself, because a
hand-kept copy is how the last point went unnoticed. The point is that a field
which the far end silently discards or mangles fails a test on this side first.
"""

from __future__ import annotations

import ast
import importlib
import math
from pathlib import Path
import re

from .conftest import PACKAGE

stats_extra = importlib.import_module(f"{PACKAGE}.stats_extra")



def _stats_py_extra_keys() -> set[str]:
    """EXTRA_KEYS as written in stats.py, read without importing it.

    stats.py pulls in Home Assistant, which these tests run without.
    """
    source = Path(__file__).resolve().parent.parent / (
        "custom_components/nibe_local_easyconf/stats.py"
    )
    for node in ast.parse(source.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            getattr(target, "id", None) == "EXTRA_KEYS" for target in node.targets
        ):
            return set(ast.literal_eval(node.value))
    raise AssertionError("EXTRA_KEYS not found in stats.py")


#: stats.py: the only keys the integration's extra callback may contribute.
STATS_EXTRA_KEYS = _stats_py_extra_keys()

#: lib/ingest.ts ALLOWED_KEYS. An unknown key rejects the whole report.
ALLOWED_KEYS = {
    "schema", "install_id", "integration", "version", "ha_version", "ha_type",
    "python_version", "country", "language", "entities", "devices", "models",
    "features", "errors", "lat", "lon", "metrics", "firmware", "firmwares",
}

#: lib/ingest.ts METRICS, the entries that concern this integration.
METRICS = {
    "built_year": {"max": 2100, "min": 1990, "dec": 0},
    "built_week": {"max": 53, "min": 1, "dec": 0},
    "product_code": {"max": 9999, "min": 1000, "dec": 0},
    "cop_day": {"max": 10, "min": 0.5, "dec": 2},
    "cop_year": {"max": 10, "min": 0.5, "dec": 2},
    "cop_lifetime": {"max": 10, "min": 0.5, "dec": 2},
}

RE_MODEL = re.compile(r"^[a-z0-9][a-z0-9._-]{0,31}$")
RE_FEATURE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
RE_VERSION = re.compile(r"^[0-9A-Za-z][0-9A-Za-z._+-]{0,31}$")
MAX_FEATURES = 24
MAX_FEATURE_VALUE = 100000


def _clamp(value, spec):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    if not math.isfinite(value):
        return None
    bounded = min(spec["max"], max(spec.get("min", 0), value))
    return round(bounded * 10 ** spec["dec"]) / 10 ** spec["dec"]


def _full_report():
    return stats_extra.build_extra(
        "s1155",
        traits={"ground_source", "hot_water", "cooling"},
        registers_present=919,
        registers_reporting=882,
        registers_absent=303,
        entities_enabled=96,
        block_reads=58,
        scan_interval_s=60,
        read_failures=2,
        firmware=1036,
        serial="06544322034003",
        cop_day=3.91,
        cop_year=3.98,
        cop_lifetime=4.18,
    )


def test_stats_py_passes_every_key_through():
    """Anything outside stats.py's list is dropped before the wire."""
    assert set(_full_report()) <= STATS_EXTRA_KEYS


def test_backend_accepts_every_top_level_key():
    """One unknown top-level key rejects the entire report with a 400."""
    assert set(_full_report()) <= ALLOWED_KEYS


def test_every_metric_is_one_the_backend_keeps():
    for key in _full_report().get("metrics", {}):
        assert key in METRICS, f"backend would silently drop metric {key!r}"


def test_no_metric_is_changed_by_the_backend_clamp():
    """The product_code bug: 65443 in, 9999 stored, no error anywhere."""
    for key, value in _full_report().get("metrics", {}).items():
        assert _clamp(value, METRICS[key]) == value, f"{key}={value} would be clamped"


def test_every_model_is_stored_verbatim():
    for model in _full_report()["models"]:
        assert RE_MODEL.match(model.lower()), f"model {model!r} would be dropped"


def test_the_article_number_survives():
    assert "065443" in _full_report()["models"]


def test_every_feature_survives():
    features = _full_report()["features"]
    assert len(features) <= MAX_FEATURES
    for key, value in features.items():
        assert RE_FEATURE.match(key), f"feature {key!r} would be dropped"
        if not isinstance(value, bool):
            assert 0 <= value <= MAX_FEATURE_VALUE, f"feature {key}={value} would be clamped"


def test_firmware_survives():
    firmware = _full_report()["firmware"]
    assert isinstance(firmware, str)
    assert RE_VERSION.match(firmware)


def test_every_cop_figure_survives():
    metrics = _full_report()["metrics"]
    assert metrics["cop_day"] == 3.91
    assert metrics["cop_year"] == 3.98
    assert metrics["cop_lifetime"] == 4.18
