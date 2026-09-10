"""Make the pure-logic modules importable without pulling in Home Assistant.

`custom_components/nibe_local_easyconf/__init__.py` imports homeassistant, but
the modules under test here (codec, discovery, descriptions, const, registry)
do not. Registering the directory as a package by hand means Python resolves
their relative imports without ever executing that `__init__`, so the suite
runs in a second and needs nothing but the `nibe` register maps.
"""

from __future__ import annotations

from pathlib import Path
import sys
import types

PACKAGE = "nibe_easyconf_under_test"
SOURCE = Path(__file__).resolve().parents[1] / "custom_components" / "nibe_local_easyconf"

if PACKAGE not in sys.modules:
    module = types.ModuleType(PACKAGE)
    module.__path__ = [str(SOURCE)]
    sys.modules[PACKAGE] = module
