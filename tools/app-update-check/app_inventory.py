#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_inventory.py — 記錄這台 Mac 上「所有」已安裝 App 的清冊，並累積新增／移除紀錄。

由 check_updates.py 每次執行時呼叫（也可單獨執行：python3 app_inventory.py）。
用途：給 mac-health-check skill 判斷「哪些 App 已被移除」，再用識別碼
（bundle id）去 ~/Library 找對應的殘留檔案。

產出（與本檔同資料夾）：
  inventory.json          目前的完整清冊（每次覆寫）
  inventory_changes.jsonl 累積的變動紀錄，一行一筆，只增不刪：
                          {"date", "change": "removed"/"added"/"baseline", "name",
                           "bundle_id", "version", "path"}

設計重點：
  - 只讀取、不修改任何 App。只用 Python 標準函式庫，相容 macOS 內建 python3。
  - 掃描失敗或掃到的數量異常少（少於上次的一半）時，不覆寫清冊、不寫變動，
    避免權限問題（例如排程在背景跑時被 macOS 擋住）把所有 App 誤判成「已移除」。
  - 版本升級、App 換位置不算變動，只記錄「新增」與「移除」。
"""

import json
import os
import plistlib
import sys
from datetime import datetime, timezone, timedelta

TAIPEI = timezone(timedelta(hours=8))

# 掃描範圍：(資料夾, 來源標記)。子資料夾只往下找一層（例如 SketchUp 2026/、Utilities/）
DEFAULT_ROOTS = [
    ("/Applications", "applications"),
    ("/System/Applications", "system"),
    (os.path.expanduser("~/Applications"), "user"),
]

INVENTORY = "inventory.json"
CHANGES = "inventory_changes.jsonl"


def _read_app(path, source):
    plist = os.path.join(path, "Contents", "Info.plist")
    try:
        with open(plist, "rb") as f:
            info = plistlib.load(f)
    except Exception:
        info = {}
    name = os.path.basename(path)[:-4]
    receipt = os.path.join(path, "Contents", "_MASReceipt", "receipt")
    try:
        mas = os.path.getsize(receipt) > 0
    except OSError:
        mas = False
    return {
        "name": name,
        "bundle_id": info.get("CFBundleIdentifier"),
        "version": info.get("CFBundleShortVersionString") or info.get("CFBundleVersion"),
        "path": path,
        "source": source,
        "app_store": mas,
    }


def scan(roots=None):
    """回傳 (apps, errors)。/Applications 本身讀不到時 errors 會有內容。"""
    roots = roots or DEFAULT_ROOTS
    apps, errors = [], []
    for root, source in roots:
        try:
            entries = sorted(os.listdir(root))
        except FileNotFoundError:
            continue  # 例如 ~/Applications 不存在，屬正常
        except OSError as e:
            errors.append(f"{root}: {e}")
            continue
        for entry in entries:
            path = os.path.join(root, entry)
            if entry.endswith(".app"):
                apps.append(_read_app(path, source))
            elif os.path.isdir(path) and not entry.startswith("."):
                try:
                    for sub in sorted(os.listdir(path)):
                        if sub.endswith(".app"):
                            apps.append(_read_app(os.path.join(path, sub), source))
                except OSError:
                    continue
    return apps, errors


def _key(app):
    return app.get("bundle_id") or app.get("path")


def update(out_dir=None, roots=None, now=None):
    """掃描並更新清冊。回傳 dict：{"status", "removed", "added", "count", "message"}。"""
    out_dir = out_dir or os.path.dirname(os.path.abspath(__file__))
    now = (now or datetime.now(TAIPEI)).isoformat(timespec="seconds")
    inv_path = os.path.join(out_dir, INVENTORY)
    chg_path = os.path.join(out_dir, CHANGES)

    apps, errors = scan(roots)
    prev = None
    try:
        with open(inv_path, encoding="utf-8") as f:
            prev = json.load(f)
    except (FileNotFoundError, ValueError):
        prev = None

    prev_apps = (prev or {}).get("apps", [])
    if not apps:
        detail = ("：" + "; ".join(errors)) if errors else ""
        return {"status": "skipped", "removed": [], "added": [], "count": 0,
                "message": "沒有掃到任何 App，這次不更新清冊" + detail}
    if prev_apps and len(apps) < len(prev_apps) * 0.5:
        return {"status": "skipped", "removed": [], "added": [], "count": len(apps),
                "message": f"這次只掃到 {len(apps)} 個 App（上次 {len(prev_apps)} 個），"
                           "數量異常，疑似權限問題，這次不更新清冊"}

    cur = {_key(a): a for a in apps}
    old = {_key(a): a for a in prev_apps}
    removed = [old[k] for k in sorted(old) if k not in cur]
    added = [cur[k] for k in sorted(cur) if k not in old] if prev is not None else []

    lines = []
    if prev is None:
        lines.append({"date": now, "change": "baseline", "count": len(apps)})
    for change, items in (("removed", removed), ("added", added)):
        for a in items:
            lines.append({"date": now, "change": change, "name": a.get("name"),
                          "bundle_id": a.get("bundle_id"), "version": a.get("version"),
                          "path": a.get("path")})
    if lines:
        with open(chg_path, "a", encoding="utf-8") as f:
            for line in lines:
                f.write(json.dumps(line, ensure_ascii=False) + "\n")

    tmp = inv_path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"generated_at": now, "count": len(apps), "apps": apps},
                  f, ensure_ascii=False, indent=2)
    os.replace(tmp, inv_path)

    if prev is None:
        msg = f"已建立 App 清冊基準（{len(apps)} 個 App）"
    elif removed or added:
        parts = []
        if removed:
            parts.append("已移除：" + "、".join(a["name"] for a in removed))
        if added:
            parts.append("新安裝：" + "、".join(a["name"] for a in added))
        msg = "App 清冊有變動｜" + "；".join(parts)
    else:
        msg = f"App 清冊無變動（{len(apps)} 個 App）"
    return {"status": "ok", "removed": removed, "added": added,
            "count": len(apps), "message": msg}


if __name__ == "__main__":
    result = update()
    print(result["message"])
    sys.exit(0 if result["status"] == "ok" else 1)
