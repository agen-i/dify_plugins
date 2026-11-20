from pathlib import Path
import subprocess
import sys

import yaml

APP = Path(__file__).resolve().parents[1]


def test_current_author_repository_contact_and_single_tool():
    manifest = yaml.safe_load((APP / "manifest.yaml").read_text())
    provider = yaml.safe_load((APP / "provider/read_region.yaml").read_text())
    tool = yaml.safe_load((APP / "tools/read_region.yaml").read_text())
    assert manifest["version"] == "0.4.3"
    assert (
        manifest["author"]
        == provider["identity"]["author"]
        == tool["identity"]["author"]
        == "agen-i"
    )
    assert manifest["repo"] == "https://github.com/agen-i/dify_plugins"
    assert manifest["contact"] == "contact@agen-i.com"
    assert (
        set(manifest["plugins"]) == {"tools"}
        and provider["credentials_for_provider"] == {}
    )
    assert (APP / "LICENSE").read_text().find("Copyright") >= 0


def test_pinned_sdk_provider_schema_validates_new_namespace():
    subprocess.run(
        [
            sys.executable,
            "-c",
            "import yaml; from dify_plugin.entities.tool import ToolProviderConfiguration; p=ToolProviderConfiguration.model_validate(yaml.safe_load(open('provider/read_region.yaml'))); assert p.identity.author=='agen-i'; assert p.tools[0].identity.author=='agen-i'",
        ],
        cwd=APP,
        check=True,
        capture_output=True,
    )
