"""Resolve shared series canon without silently overriding episode decisions."""

from pathlib import Path

from .io import inside, read_json, read_json_hashed
from .validation import Finding, validate


def load_episode(path):
    path = Path(path)
    data, source_hash = read_json_hashed(path)
    inputs = {"episode": source_hash}
    if not isinstance(data, dict) or "canon_ref" not in data:
        return data, inputs
    ref = data["canon_ref"]
    if not isinstance(ref, str) or not ref.strip() or Path(ref).is_absolute():
        raise ValueError("canon_ref 须为相对路径")
    if set(data) != {"schema_version", "canon_ref", "project", "beats", "initial_state", "shots"}:
        raise ValueError("共享设定模式仅允许 schema_version、canon_ref、project、beats、initial_state、shots")
    episode_project = data["project"]
    if not isinstance(episode_project, dict) or not {"id", "title"} <= episode_project.keys() or episode_project.keys() - {"id", "title", "dialogue_cps_warning"}:
        raise ValueError("共享设定模式的单集 project 仅允许 id、title、dialogue_cps_warning")
    canon_path = (path.parent / ref).resolve()
    canon, canon_hash = read_json_hashed(canon_path)
    if not isinstance(canon, dict) or set(canon) != {"canon_version", "project", "characters", "pronunciation_lexicon"} or canon["canon_version"] != "0.1":
        raise ValueError("共享设定不符合 canon_version 0.1")
    if not isinstance(canon["project"], dict) or set(canon["project"]) != {"language", "aspect_ratio", "visual_style", "canon_facts", "negative_prompt"}:
        raise ValueError("共享 project 须包含 language、aspect_ratio、visual_style、canon_facts、negative_prompt")
    inputs["canon"] = canon_hash
    resolved = {key: value for key, value in data.items() if key != "canon_ref"}
    resolved["project"] = {**canon["project"], **episode_project}
    resolved["characters"] = canon["characters"]
    resolved["pronunciation_lexicon"] = canon["pronunciation_lexicon"]
    return resolved, inputs


def validate_series(path):
    path = Path(path)
    series = read_json(path)
    findings = []

    def error(where, message):
        findings.append(Finding("error", "S001", where, message))

    if not isinstance(series, dict) or set(series) != {"series_version", "id", "continuous", "episodes"} or series.get("series_version") != "0.1":
        error("series", "须为 series_version 0.1，包含 id、continuous、episodes")
        return findings
    if not isinstance(series["id"], str) or not series["id"].strip() or type(series["continuous"]) is not bool:
        error("series", "id 须为非空字符串，continuous 须为布尔值")
    episodes = series["episodes"]
    if not isinstance(episodes, list) or not episodes:
        error("series.episodes", "须为非空的单集相对路径数组")
        return findings
    seen_paths, seen_ids = set(), set()
    shared_canon, previous_state = None, None
    for index, relative in enumerate(episodes):
        where = f"series.episodes[{index}]"
        try:
            episode_path = inside(path.parent, relative)
            if episode_path in seen_paths:
                raise ValueError("重复的单集路径")
            seen_paths.add(episode_path)
            data, inputs = load_episode(episode_path)
            result = validate(data)
            findings.extend(Finding(x.level, x.code, f"{relative}:{x.path}", x.message) for x in result)
            if any(x.level == "error" for x in result):
                continue
            if "canon" not in inputs:
                raise ValueError("系列中的单集须使用 canon_ref 共享设定")
            if shared_canon is not None and shared_canon != inputs["canon"]:
                error(where, "系列内共享设定内容不一致")
            shared_canon = inputs["canon"]
            episode_id = data["project"]["id"]
            if episode_id in seen_ids:
                error(where, f"重复单集 ID：{episode_id}")
            seen_ids.add(episode_id)
            if series["continuous"] and previous_state is not None and data["initial_state"] != previous_state:
                error(where, "连续系列的单集初始状态与上一集结束状态不一致")
            previous_state = data["shots"][-1]["state_after"]
        except (OSError, ValueError) as exc:
            error(where, str(exc))
    return findings
