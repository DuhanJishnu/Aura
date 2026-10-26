import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_frontend_helpers_pass_their_node_tests():
    out = subprocess.run(["node", "frontend/util.test.js"], cwd=ROOT, capture_output=True, text=True, timeout=30)
    assert out.returncode == 0, out.stderr
    assert "passed" in out.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_page_scripts_are_syntactically_valid():
    for f in ("app.js", "util.js"):
        assert subprocess.run(["node", "--check", f"frontend/{f}"], cwd=ROOT, capture_output=True).returncode == 0


def test_the_page_loads_the_helpers_before_the_app_and_exposes_voice_controls():
    html = TestClient(app).get("/").text
    assert html.index("util.js") < html.index("app.js")
    for hook in ('id="mic"', 'id="speakBtn"', 'id="voiceStatus"', 'data-q="I\'m looking for clothes"'):
        assert hook in html
