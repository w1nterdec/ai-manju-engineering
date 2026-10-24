"""Decimal prices and append-only transactional budget reservations."""
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import sqlite3

from .safeio import canonical, fingerprint


def money(value):
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise ValueError("金额必须是非负十进制数") from exc
    if not number.is_finite() or number < 0:
        raise ValueError("金额必须是有限非负数")
    return number


def provenance(value):
    if not isinstance(value, dict) or type(value.get("example")) is not bool:
        raise ValueError("价格/换算须注明 example")
    try:
        date.fromisoformat(value["as_of"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("价格/换算须注明 ISO as_of 日期") from exc
    if not isinstance(value.get("source_url"), str) or not value["source_url"].startswith(("https://", "http://")):
        raise ValueError("价格/换算须包含 source_url")


def price(config, task, route):
    pricing = config["pricing"]
    provenance(pricing)
    rates = pricing.get("rates", {})
    resolution = route.get("parameters", {}).get("resolution", "preview")
    rate = rates.get(f"{route['provider']}:{route['model']}:{resolution}", rates.get(f"{route['provider']}:{route['model']}", rates.get(task["kind"], rates.get("default"))))
    if not isinstance(rate, dict) or rate.get("unit") not in ("item", "second", "credit"):
        raise ValueError("缺少 item/second/credit 计价配置")
    per = rate.get("per", "item") if rate["unit"] == "credit" else rate["unit"]
    if per not in ("item", "second"):
        raise ValueError("积分 per 仅支持 item/second")
    units = Decimal(task["parameters"].get("duration_ms", 0)) / 1000 if per == "second" else Decimal(1)
    original = money(rate.get("amount")) * units
    source = rate.get("credit_source", "default") if rate["unit"] == "credit" else rate.get("currency", pricing["currency"])
    amount = original
    conversion_key = f"credit:{source}" if rate["unit"] == "credit" else (f"{source}->{pricing['currency']}" if source != pricing["currency"] else None)
    if conversion_key:
        conversion = pricing.get("conversions", {}).get(conversion_key)
        provenance(conversion)
        amount *= money(conversion.get("to_internal"))
    return {"amount": str(amount), "currency": pricing["currency"], "original_amount": str(original), "unit": rate["unit"], "source": source, "pricing_sha256": fingerprint(pricing), "example": pricing["example"]}


def estimate(plan, config):
    minimum, maximum = Decimal(0), Decimal(0)
    attempts = config.get("execution", {}).get("max_attempts", 1)
    if type(attempts) is not int or not 1 <= attempts <= 20:
        raise ValueError("max_attempts 必须在 1..20")
    details = []
    for task in plan["tasks"]:
        if task["kind"] == "human_review":
            continue
        candidates = [price(config, task, route) for route in task["route"]]
        low = money(candidates[0]["amount"])
        high = sum((money(candidate["amount"]) for candidate in candidates), Decimal(0)) * attempts
        minimum += low
        maximum += high
        details.append({"task_id": task["id"], "min": str(low), "max": str(high)})
    return {"estimate_version": "1.0", "currency": config["pricing"]["currency"], "min": str(minimum), "max": str(maximum), "example": config["pricing"]["example"], "assumptions": "按所选分辨率的配置路由费率；上界包含全部回退与重试；不含未配置税费/人工，不是供应商报价。", "tasks": details}


class BudgetExceeded(ValueError):
    pass


class CostLedger:
    def __init__(self, path, config):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.config = config
        self.db.execute("CREATE TABLE IF NOT EXISTS ledger(id TEXT PRIMARY KEY, task_id TEXT, task_key TEXT, attempt INTEGER, type TEXT, amount TEXT, currency TEXT, project TEXT, episode TEXT, shot TEXT, batch TEXT, detail TEXT)")
        self.db.commit()

    def close(self):
        self.db.close()

    def reserve(self, run_id, plan, task, attempt):
        prices = [price(self.config, task, route) for route in task["route"]]
        amount = sum((money(item["amount"]) for item in prices), Decimal(0))
        currency = self.config["pricing"]["currency"]
        scope = self.config.get("scope", {})
        project, episode = str(scope.get("project", "local-project")), str(plan.get("project_id", "episode"))
        batch, shot = str(scope.get("batch", "default")), task["shot_id"] or ""
        key = fingerprint({"run": run_id, "key": task["key"], "attempt": attempt})
        self.db.execute("BEGIN IMMEDIATE")
        try:
            if self.db.execute("SELECT id FROM ledger WHERE id=?", (key,)).fetchone():
                self.db.commit()
                return key
            rows = list(self.db.execute("SELECT * FROM ledger WHERE project=?", (project,)))
            if any(row["currency"] != currency for row in rows):
                raise ValueError("同项目台账内部币种不同，需显式换算或新建项目账本")
            limits = self.config.get("budgets", {})
            for level in ("project", "episode", "shot", "batch"):
                if level not in limits:
                    raise ValueError(f"预算缺失：{level}")
                cap = money(limits[level])
                selected = rows
                if level in ("episode", "shot"):
                    selected = [row for row in rows if row["episode"] == episode]
                if level == "shot":
                    if not shot:
                        continue
                    selected = [row for row in selected if row["shot"] == shot]
                if level == "batch":
                    selected = [row for row in rows if row["batch"] == batch]
                spent = sum((Decimal(row["amount"]) for row in selected), Decimal(0))
                if spent + amount > cap:
                    raise BudgetExceeded(f"{level} 预算超限：已占用 {spent}，本次需 {amount}，上限 {cap} {currency}")
            detail = canonical({"prices": prices, "mock": plan["mock"]}).decode()
            self.db.execute("INSERT INTO ledger VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (key, task["id"], task["key"], attempt, "reserve", str(amount), currency, project, episode, shot, batch, detail))
            self.db.commit()
            return key
        except BaseException:
            self.db.rollback()
            raise

    def settle(self, key, success, actual=None):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            row = self.db.execute("SELECT * FROM ledger WHERE id=?", (key,)).fetchone()
            if row is None:
                raise ValueError("成本预留不存在")
            charged = money(actual) if actual is not None else money(row["amount"])
            if charged > money(row["amount"]):
                raise ValueError("实际费用超过已预留上界，禁止静默超支")
            for kind, amount in (("release", str(-Decimal(row["amount"]))), ("actual", str(charged))):
                values = list(row)
                values[0], values[4], values[5] = key + ":" + kind, kind, amount
                values[-1] = canonical({"mock": True, "success": success, "basis": "模拟计费，非真实账单", "reservation": key}).decode()
                self.db.execute("INSERT OR IGNORE INTO ledger VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", values)
            self.db.commit()
        except BaseException:
            self.db.rollback()
            raise

    def report(self):
        rows = [dict(row) for row in self.db.execute("SELECT * FROM ledger ORDER BY rowid")]
        totals = {}
        for row in rows:
            total = totals.setdefault(row["currency"], {"actual": Decimal(0), "reserved": Decimal(0), "effective": Decimal(0)})
            total["effective"] += Decimal(row["amount"])
            total["actual" if row["type"] == "actual" else "reserved"] += Decimal(row["amount"])
        return {"ledger_version": "1.0", "totals": {key: {k: str(v) for k, v in value.items()} for key, value in totals.items()}, "entries": rows, "notice": "mock 实际值仅为模拟计费；不是供应商账单；不同币种分开。"}
