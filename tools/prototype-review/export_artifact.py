"""Export an existing three-file build dossier for independent browser review.

No provider invocation, server import, database mutation or publication.
"""

import argparse
import hashlib
import json
from pathlib import Path


def export_artifact(source: Path, output: Path) -> dict:
    dossier = json.loads(source.read_text(encoding="utf-8"))
    files = dossier.get("scaffold_files")
    if not isinstance(files, list) or len(files) != 3:
        raise ValueError("Expected a three-file browser BuildDossier (scaffold_files)")
    names = [file.get("path") for file in files]
    if len(set(names)) != 3 or set(names) != {"index.html", "styles.css", "app.js"}:
        raise ValueError("Only index.html, styles.css and app.js are accepted; unsafe/extra paths rejected")
    if any(not isinstance(file.get("content"), str) or not file["content"].strip() for file in files):
        raise ValueError("Every file must contain nonempty text")
    artifact = {
        "files": sorted(
            [{"path": f["path"], "content": f["content"]} for f in files], key=lambda f: f["path"]
        )
    }
    digest = hashlib.sha256(
        json.dumps(
            artifact, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode()
    ).hexdigest()
    # Refuse to overwrite any previous artifact or evidence directory.
    output.mkdir(parents=True, exist_ok=False)
    manifest = {"artifact_sha256": digest, "browser_verified": False, "accepted": False, "files": {}}
    for file in files:
        payload = file["content"].encode("utf-8")
        (output / file["path"]).write_bytes(payload)
        manifest["files"][file["path"]] = hashlib.sha256(payload).hexdigest()
    (output / "artifact-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dossier", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(export_artifact(args.dossier, args.output), indent=2))
