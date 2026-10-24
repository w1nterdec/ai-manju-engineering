"""Strict, UTF-8 JSON and stable SHA-256 helpers."""

import hashlib
import json
from pathlib import Path


def digest(path):
    hasher = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON 重复键：{key}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"JSON 不允许非有限数值：{value}")


def read_json(path):
    return read_json_hashed(path)[0]


def digest_bytes(content):
    return hashlib.sha256(content).hexdigest()


def read_json_hashed(path):
    content = Path(path).read_bytes()
    data = json.loads(content.decode("utf-8-sig"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
    return data, digest_bytes(content)


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def inside(root, relative):
    """Resolve a build artifact without allowing paths outside its build directory."""
    if not isinstance(relative, str) or not relative.strip() or Path(relative).is_absolute():
        raise ValueError("产物路径必须是构建目录内的相对路径")
    target = (Path(root) / relative).resolve()
    if not target.is_relative_to(Path(root).resolve()):
        raise ValueError("产物路径越过构建目录边界")
    return target
