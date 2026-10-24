"""Deterministic execution plans derived without modifying legacy build files."""
from pathlib import Path

from .adapters import load_config, registry, route_for
from .io import digest, read_json
from .review import load_bundle
from .safeio import fingerprint


def make_plan(bundle, config=None):
    bundle = Path(bundle)
    manifest = load_bundle(bundle)
    config = config or load_config()
    episode = read_json(bundle / "episode.snapshot.json")
    shots = {shot["id"]: shot for shot in episode["shots"]}
    voices = {line["line_id"]: line for line in read_json(bundle / "voice_plan.json")}
    chars = {char["id"]: char for char in episode["characters"]}
    providers = registry()
    tasks = []
    for char_id, char in chars.items():
        tasks.append({"id": f"identity:{char_id}", "kind": "identity", "depends_on": [], "parameters": {"character": char, "identity": config.get("identities", {}).get(char_id)}, "shot_id": None})
    for original in read_json(bundle / "tasks.json"):
        task = {key: original[key] for key in ("id", "kind", "depends_on")}
        task["depends_on"] = list(task["depends_on"])
        if task["kind"] == "tts":
            voice = voices[task["id"].split(":", 1)[1]]
            task["shot_id"] = voice["shot_id"]
            task["parameters"] = {"voice": voice, "duration_ms": voice["planned_end_ms"] - voice["planned_start_ms"]}
        elif task["kind"] in ("image", "video", "human_review"):
            shot_id = task["id"].split(":", 1)[1]
            shot = shots[shot_id]
            task["shot_id"] = shot_id
            task["parameters"] = {"shot": shot, "duration_ms": shot["duration_ms"], "project": {k: v for k, v in episode["project"].items() if k not in ("title", "id")}, "prompt_sha256": digest(bundle / "shots" / f"{shot_id}.md")}
            if task["kind"] == "image":
                task["depends_on"].extend(f"identity:{cid}" for cid in shot["character_ids"])
        else:
            task["shot_id"] = None
            task["parameters"] = {"duration_ms": manifest["planned_duration_ms"], "timeline": manifest["shots"]}
        tasks.append(task)
    by_id = {task["id"]: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("执行计划出现重复任务")
    visiting, done = set(), set()

    def resolve(task_id):
        if task_id not in by_id or task_id in visiting:
            raise ValueError("执行计划依赖缺失或成环")
        task = by_id[task_id]
        if task_id in done:
            return task["key"]
        visiting.add(task_id)
        dependencies = [resolve(dep) for dep in task["depends_on"]]
        route = [] if task["kind"] == "human_review" else route_for(config, task["kind"], task["shot_id"])
        for candidate in route:
            providers.get(candidate["provider"]).capabilities.require(task["kind"], task["parameters"])
        task["route"] = route
        task["key"] = fingerprint({"id": task_id, "parameters": task["parameters"], "route": route, "dependencies": dependencies})
        visiting.remove(task_id)
        done.add(task_id)
        return task["key"]

    for task in tasks:
        resolve(task["id"])
    result = {"plan_version": "1.0", "mock": all(providers.get(route["provider"]).capabilities.offline for task in tasks for route in task["route"]), "manifest_sha256": digest(bundle / "manifest.json"), "config_sha256": fingerprint(config), "tasks": tasks}
    result["plan_id"] = fingerprint(result)
    return result
