"""Identity of checkpoint-interpreting code and relevant installed runtimes."""

import hashlib
import sys
from importlib.metadata import version
from pathlib import Path


def execution_fingerprint() -> str:
    root = Path(__file__).parent
    digest = hashlib.sha256(b"approved-brief-execution-v1\n")
    digest.update(f"python:{sys.version_info.major}.{sys.version_info.minor}\n".encode())
    for name in ("langgraph", "langgraph-checkpoint-sqlite", "pydantic", "sqlalchemy"):
        digest.update(f"{name}:{version(name)}\n".encode())
    for path in sorted(root.rglob("*.py")):
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(path.read_bytes().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()
