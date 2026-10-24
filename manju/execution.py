"""Single-writer SQLite event journal with bounded concurrent offline workers."""
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
import time

from .adapters import WorkRequest, registry
from .io import digest, inside
from .safeio import atomic_json, canonical, redact, run_lock


class Engine:
    def __init__(self, directory, config):
        self.root = Path(directory)
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "artifacts").mkdir(exist_ok=True)
        self.config = config
        self.registry = registry()
        self.db = sqlite3.connect(self.root / "run.sqlite3", timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS tasks(id TEXT PRIMARY KEY, key TEXT, state TEXT, attempts INTEGER, result TEXT, error TEXT);
        CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, task_id TEXT, event TEXT, payload TEXT);
        CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def event(self, task_id, event, payload=None):
        self.db.execute("INSERT INTO events(at,task_id,event,payload) VALUES(?,?,?,?)", (datetime.now(timezone.utc).isoformat(), task_id, event, canonical(redact(payload or {})).decode("utf-8")))

    def state(self):
        return {row["id"]: dict(row) for row in self.db.execute("SELECT * FROM tasks ORDER BY id")}

    def sync(self, plan):
        rows = self.state()
        for row in rows.values():
            if row["state"] == "succeeded" and row["result"]:
                result = json.loads(row["result"])
                if "path" in result:
                    path = inside(self.root / "artifacts", result["path"])
                    if not path.is_file() or digest(path) != result["sha256"]:
                        raise ValueError("已成功任务的产物缺失或被修改，拒绝复用")
        current_ids = {task["id"] for task in plan["tasks"]}
        for old in rows.keys() - current_ids:
            self.db.execute("DELETE FROM tasks WHERE id=?", (old,))
            self.event(old, "removed")
        for task in plan["tasks"]:
            old = rows.get(task["id"])
            if old is None:
                self.db.execute("INSERT INTO tasks VALUES(?,?,?,0,NULL,NULL)", (task["id"], task["key"], "pending"))
                self.event(task["id"], "pending", {"key": task["key"]})
            elif old["key"] != task["key"]:
                self.db.execute("UPDATE tasks SET key=?,state='stale',attempts=0,result=NULL,error=NULL WHERE id=?", (task["key"], task["id"]))
                self.event(task["id"], "stale", {"previous_key": old["key"], "key": task["key"]})
            elif old["state"] == "running":
                offline = all(self.registry.get(route["provider"]).capabilities.offline for route in task["route"])
                next_state = "pending" if offline else "needs_review"
                self.db.execute("UPDATE tasks SET state=? WHERE id=?", (next_state, task["id"]))
                self.event(task["id"], "recovered", {"state": next_state, "reason": "idempotent offline recovery" if offline else "provider reconciliation required"})
        self.db.execute("INSERT OR REPLACE INTO meta VALUES('plan_id',?)", (plan["plan_id"],))
        self.db.commit()
        atomic_json(self.root / "plan.json", plan)

    def _generate(self, task, attempt):
        failures = self.config.get("simulation", {}).get("fail_first", {}).get(task["id"], 0)
        if attempt <= failures:
            raise RuntimeError("mock transient failure")
        errors = []
        for candidate in task["route"]:
            provider = self.registry.get(candidate["provider"])
            if not provider.capabilities.offline:
                raise ValueError("本版本执行器禁止真实生成调用；需经验证的真实适配器与调用准入")
            request = WorkRequest(task["id"], task["kind"], candidate["model"], task["key"], task["parameters"])
            try:
                result = provider.generate(request, self.root / "artifacts")
                result["provider"] = candidate["provider"]
                return result
            except (OSError, ValueError, RuntimeError) as exc:
                errors.append(redact(str(exc)))
        raise RuntimeError("路由全部失败：" + "; ".join(errors))

    def run(self, plan, *, auto_review_mock=False, stop_after=None, retry_failed=False):
        settings = self.config.get("execution", {})
        concurrency, attempts = settings.get("concurrency", 1), settings.get("max_attempts", 1)
        backoff = settings.get("backoff_seconds", 0)
        if type(concurrency) is not int or not 1 <= concurrency <= 32 or type(attempts) is not int or not 1 <= attempts <= 20 or type(backoff) not in (int, float) or not 0 <= backoff <= 60:
            raise ValueError("执行参数越界：并发 1..32、尝试 1..20、退避 0..60 秒")
        if auto_review_mock and not plan["mock"]:
            raise ValueError("只有全 mock 计划允许模拟审核")
        with run_lock(self.root):
            self.sync(plan)
            if retry_failed:
                self.db.execute("UPDATE tasks SET state='pending',attempts=0 WHERE state='failed'")
                self.event(None, "retry_failed", {"note": "explicit manual retry; prior costs retained"})
                self.db.commit()
            in_flight, ready_at, completed = {}, {}, 0
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                while True:
                    if (self.root / "cancel.json").exists() or (stop_after is not None and completed >= stop_after):
                        self.event(None, "paused", {"reason": "cancel requested or stop limit"})
                        self.db.commit()
                        # In-flight work finishes and is journaled before returning.
                        stopped = True
                    else:
                        stopped = False
                    rows = self.state()
                    if not stopped:
                        for task in plan["tasks"]:
                            row = rows[task["id"]]
                            if len(in_flight) >= concurrency:
                                break
                            if row["state"] not in ("pending", "stale", "needs_review") or any(rows[dep]["state"] != "succeeded" for dep in task["depends_on"]):
                                continue
                            if task["kind"] == "human_review":
                                if auto_review_mock:
                                    self.db.execute("UPDATE tasks SET state='succeeded',result=? WHERE id=?", (canonical({"mock": True, "review_type": "simulated", "key": task["key"]}).decode(), task["id"]))
                                    self.event(task["id"], "simulated_review", {"mock": True})
                                elif row["state"] != "needs_review":
                                    self.db.execute("UPDATE tasks SET state='needs_review' WHERE id=?", (task["id"],))
                                    self.event(task["id"], "needs_review")
                                self.db.commit()
                                continue
                            if row["state"] == "needs_review" or time.monotonic() < ready_at.get(task["id"], 0):
                                continue
                            attempt = row["attempts"] + 1
                            self.db.execute("UPDATE tasks SET state='running',attempts=?,error=NULL WHERE id=?", (attempt, task["id"]))
                            self.event(task["id"], "running", {"attempt": attempt, "key": task["key"]})
                            self.db.commit()
                            in_flight[pool.submit(self._generate, task, attempt)] = (task, attempt)
                    if not in_flight:
                        rows = self.state()
                        runnable = any(row["state"] in ("pending", "stale") and all(rows[d]["state"] == "succeeded" for d in task["depends_on"]) for task in plan["tasks"] for row in [rows[task["id"]]])
                        newly_simulated = any(task["kind"] == "human_review" and rows[task["id"]]["state"] == "succeeded" for task in plan["tasks"])
                        if stopped or (not runnable and not (auto_review_mock and newly_simulated and any(r["state"] == "pending" for r in rows.values()))):
                            break
                        if not runnable:
                            break
                        time.sleep(0.01)
                        continue
                    finished, _ = wait(in_flight, timeout=0.05, return_when=FIRST_COMPLETED)
                    for future in finished:
                        task, attempt = in_flight.pop(future)
                        try:
                            result = future.result()
                            self.db.execute("UPDATE tasks SET state='succeeded',result=? WHERE id=?", (canonical(result).decode(), task["id"]))
                            self.event(task["id"], "succeeded", result)
                            completed += 1
                        except (OSError, ValueError, RuntimeError) as exc:
                            state = "pending" if attempt < attempts else "failed"
                            self.db.execute("UPDATE tasks SET state=?,error=? WHERE id=?", (state, redact(str(exc)), task["id"]))
                            self.event(task["id"], state, {"attempt": attempt, "error": str(exc)})
                            ready_at[task["id"]] = time.monotonic() + min(60, backoff * 2 ** (attempt - 1))
                        self.db.commit()
            result = {"run_version": "1.0", "plan_id": plan["plan_id"], "mock": plan["mock"], "tasks": self.state()}
            atomic_json(self.root / "status.json", result)
            events = [dict(row) for row in self.db.execute("SELECT * FROM events ORDER BY seq")]
            atomic_json(self.root / "events.json", events)
            return result


def approve(directory, task_id, reviewer, note):
    if not reviewer.strip() or not note.strip():
        raise ValueError("实际审核人和说明不能为空")
    with run_lock(directory):
        engine = Engine(directory, {})
        try:
            row = engine.state().get(task_id)
            if row is None or row["state"] != "needs_review" or not task_id.startswith("review:"):
                raise ValueError("任务并非待人工审核的镜头")
            result = {"reviewer": reviewer, "note": note, "key": row["key"], "review_type": "human_record"}
            engine.db.execute("UPDATE tasks SET state='succeeded',result=? WHERE id=?", (canonical(result).decode(), task_id))
            engine.event(task_id, "human_record", result)
            engine.db.commit()
        finally:
            engine.close()
