import importlib.util
import json
from pathlib import Path

import pytest

from p2pops.briefs import artifact_digest

spec = importlib.util.spec_from_file_location(
    "artifact_export", Path(__file__).resolve().parents[1] / "tools/prototype-review/export_artifact.py"
)
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


def dossier():
    return {
        "scaffold_files": [
            {"path": name, "content": "source\nsecond line\n"}
            for name in ("app.js", "index.html", "styles.css")
        ]
    }


def test_export_preserves_acceptance_digest_and_refuses_overwrite(tmp_path):
    source = tmp_path / "dossier.json"
    document = dossier()
    source.write_text(json.dumps(document))
    output = tmp_path / "artifact"
    manifest = exporter.export_artifact(source, output)
    assert manifest["artifact_sha256"] == artifact_digest(document)
    assert not manifest["accepted"] and not manifest["browser_verified"]
    assert (output / "app.js").read_bytes() == b"source\nsecond line\n"
    with pytest.raises(FileExistsError):
        exporter.export_artifact(source, output)


@pytest.mark.parametrize(
    "path", ["../secret.py", "/index.html", "nested/index.html", "C:/secret.html", "app.js"]
)
def test_export_rejects_unsafe_or_duplicate_paths_before_writing(tmp_path, path):
    document = dossier()
    document["scaffold_files"][1]["path"] = path
    source = tmp_path / "dossier.json"
    source.write_text(json.dumps(document))
    output = tmp_path / "artifact"
    with pytest.raises(ValueError):
        exporter.export_artifact(source, output)
    assert not output.exists()
