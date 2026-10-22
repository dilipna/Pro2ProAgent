"""Same-host exclusion with kernel-owned locks, automatically released on death.

Lock files are stable names, not evidence that a worker is alive. Never delete
one to recover a job: deleting a locked file can create two independent locks.
"""

import os
import re
from contextlib import contextmanager
from pathlib import Path

from .config import get_settings


@contextmanager
def execution_lock(run_id: str):
    if re.fullmatch(r"[0-9a-f]{32}", run_id) is None:
        raise ValueError("invalid execution identity")
    folder = Path(get_settings().data_dir) / "execution-locks"
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / f"{run_id}.lock").open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
        handle.seek(0)
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt

                try:
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    acquired = True
                except OSError:
                    pass
            else:
                import fcntl

                try:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except BlockingIOError:
                    pass
            yield acquired
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
