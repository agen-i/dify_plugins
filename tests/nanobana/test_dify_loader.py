from __future__ import annotations

import importlib.util
import sys
import uuid

import pytest
from conftest import PLUGIN_DIR, install_dify_stubs


def test_tool_module_loads_with_dify_exec_module_style(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_dify_stubs(monkeypatch)
    monkeypatch.syspath_prepend(str(PLUGIN_DIR))
    module_name = f"dify_loader_nanobana_tool_{uuid.uuid4().hex}"
    sys.modules.pop(module_name, None)

    spec = importlib.util.spec_from_file_location(
        module_name,
        PLUGIN_DIR / "tools" / "nanobana.py",
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    assert module_name not in sys.modules

    spec.loader.exec_module(module)

    assert module_name not in sys.modules
    assert hasattr(module, "NanobanaTool")
