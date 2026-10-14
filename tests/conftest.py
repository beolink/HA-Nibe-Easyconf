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


def pytest_configure(config):
    """Run pytest-asyncio in auto mode wherever it is loaded.

    The offline suite is synchronous and never notices the mode. But
    pytest-homeassistant-custom-component, which test_gateway_homeassistant.py
    needs, brings autouse fixtures that are async, and in strict mode every
    test in the session errors at set-up over them (pytest 9 turned the
    warning into an error). Switching the mode here, rather than in
    pytest.ini, keeps an environment without pytest-asyncio, such as the CI
    job, free of a warning about an unknown option. A mode given on the
    command line, or anything but the plugin's default in the ini or through
    -o, is left as it is. The same hook as in HA-CTC-Local-Easyconf.
    """
    if not hasattr(config.option, "asyncio_mode"):
        return  # pytest-asyncio is not loaded; nothing registered the option
    if config.option.asyncio_mode is not None or config.getini("asyncio_mode") != "strict":
        return
    config.option.asyncio_mode = "auto"
