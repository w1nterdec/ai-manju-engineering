"""Atomic side-file persistence, deterministic serialization and secret redaction."""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import re
import tempfile

from .io import digest_bytes

SECRET_KEY = re.compile(r"(?i)(api.?key|access.?token|authorization|password|credential|secret)")
SECRET_VALUE = re.compile(r"(?:gh[pousr]_\w{20,}|sk-[\w-]{20,}|Bearer\s+\S+|https?://[^/\s@]+:[^/\s@]+@)", re.I)


def redact(value):
    if isinstance(value, dict):
        return {str(k): "[REDACTED]" if SECRET_KEY.search(str(k)) else redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return SECRET_VALUE.sub("[REDACTED]", value) if isinstance(value, str) else value


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def fingerprint(value):
    return digest_bytes(canonical(value))


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".atomic-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def run_lock(directory):
    """OS-held lock is automatically released on process death, on both platforms."""
    path = Path(directory) / ".run.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as stream:
        stream.seek(0, 2)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        if os.name == "nt":
            import msvcrt
            try:
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as exc:
                raise ValueError("运行目录正由另一个执行器使用") from exc
        else:
            import fcntl
            try:
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as exc:
                raise ValueError("运行目录正由另一个执行器使用") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
