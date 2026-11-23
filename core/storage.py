"""Atomic JSON state writes.

A fixed `<state>.tmp` name breaks when two threads (or a restarted thread and the old one) save at the same time: the
first replace removes the file the second is about to rename, and the save raises FileNotFoundError even though the
state itself is valid. Each save now writes its own temporary file in the same directory and replaces the target in one
step, so a reader only ever sees a complete file and concurrent writers cannot delete each other's work."""
import json
import os
import tempfile
from pathlib import Path


def write_json_atomic(path, data, **dump_kwargs):
    path = Path(path)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f"{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, **dump_kwargs)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
