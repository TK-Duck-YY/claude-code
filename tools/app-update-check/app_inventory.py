#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app_inventory.py — 記錄這台 Mac 上「所有」已安裝 App 的清冊，並累積新增／移除紀錄。

由 check_updates.py 每次執行時呼叫（也可單獨執行：python3 app_inventory.py）。
用途：給 mac-health-check skill 判斷「哪些 App 已被移除」，再用識別碼
（bundle id）去 ~/Library 找對應的殘留檔案。

掃描範圍（SCOPE_VERSION = 2，2026-11-16 起）：
  1. /Applications、/System/Applications、~/Applications 往下三層
     （例如 /Applications/Autodesk/AutoCAD 2026/AutoCAD 2026.app）。
  2. ~/Library 底下每個資料夾的第一層 .app
     （例如 ~/Library/HiPKILocalSignServer/CHTSCTokenApp.app）。
     受保護或會頻繁變動的資料夾（LIBRARY_SKIP）不進去，避免排程執行時
     跳出 macOS 權限詢問，或把暫存的更新檔誤判成新增／移除。
  不會進入 .app 內部（App 自帶的小幫手程式不列入）。

產出（與本檔同資料夾）：
  inventory.json          目前的完整清冊（每次覆寫），含 scope 版本
  inventory_changes.jsonl 累積的變動紀錄，一行一筆，只增不刪：
                          {"date", "change": "removed"/"added", "name",
                           "bundle_id", "version", "path"}
                          另有兩種標記行：
                          {"date", "change": "baseline", "count"}           第一次建立
                          {"date", "change": "scope_change", "from", "to",
                           "count", "newly_listed"}                          掃描範圍擴大

設計重點：
  - 只讀取、不修改任何 App。只用 Python 標準函式庫，相容 macOS 內建 python3。
  - 掃描失敗或掃到的數量異常少（少於上次的一半）時，不覆寫清冊、不寫變動，
    避免權限問題（例如排程在背景跑時被 macOS 擋住）把所有 App 誤判成「已移除」。
  - 版本升級、App 換位置不算變動，只記錄「新增」與「移除」。
  - 掃描範圍擴大時，新看到的 App 不記成「新增」（它們早就裝著），只寫一行
    scope_change；「移除」照常記錄。
"""

import json
import os
import plistlib
import sys
from datetime import datetime, timezone, timedelta

TAIPEI = timezone(timedelta(hours=8))

# 掃描範圍版本：1 = 三個應用程式資料夾往下一層；2 = 往下三層 + ~/Library 第一層
SCOPE_VERSION = 2

# 應用程式資料夾：(資料夾, 來源標記)，往下找 APP_ROOT_DEPTH 層
DEFAULT_ROOTS = [
    ("/Applications", "applications"),
    ("/System/Applications", "system"),
    (os.path.expanduser("~/Applications"), "user"),
]
APP_ROOT_DEPTH = 3

# ~/Library：只看每個資料夾的第一層 .app
LIBRARY = os.path.expanduser("~/Library")
LIBRARY_SKIP = {
    # 其他 App 的資料容器：讀取可能觸發 macOS「取用其他 App 的資料」詢問
    "Containers", "Group Containers", "Daemon Containers", "Application Scripts",
    # 個人資料與受保護資料夾
    "Mail", "Messages", "Safari", "Cookies", "Calendars", "Reminders", "HomeKit",
    "Photos", "Suggestions", "IdentityServices", "Accounts", "Biome",
    # 雲端與快取：可能觸發下載，或有暫存的 App 更新檔來來去去
    "CloudStorage", "Mobile Documents", "Caches", "Metadata", "Logs", "Trial",
}

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


def _walk(path, source, depth_left, apps, errors, top=False):
    """在 path 底下找 .app，最多往下 depth_left 層；不進入 .app 內部、不跟隨捷徑。"""
    try:
        entries = sorted(os.listdir(path))
    except FileNotFoundError:
        return  # 例如 ~/Applications 不存在，屬正常
    except OSError as e:
        if top:
            errors.append(f"{path}: {e}")
        return
    for entry in entries:
        if entry.startswith("."):
            continue
        full = os.path.join(path, entry)
        if entry.endswith(".app"):
            apps.append(_read_app(full, source))
        elif depth_left > 1 and os.path.isdir(full) and not os.path.islink(full):
            _walk(full, source, depth_left - 1, apps, errors)


def _scan_library(library, apps):
    """~/Library 每個資料夾的第一層 .app。讀不到的資料夾直接略過（受保護屬正常）。"""
    try:
        entries = sorted(os.listdir(library))
    except OSError:
        return
    for entry in entries:
        if entry.startswith(".") or entry in LIBRARY_SKIP:
            continue
        full = os.path.join(library, entry)
        if os.path.islink(full):
            continue
        if entry.endswith(".app"):
            apps.append(_read_app(full, "library"))
            continue
        if not os.path.isdir(full):
            continue
        try:
            subs = sorted(os.listdir(full))
        except OSError:
            continue
        for sub in subs:
            if sub.endswith(".app") and not sub.startswith("."):
                apps.append(_read_app(os.path.join(full, sub), "library"))


def scan(roots=None, library=None, depth=APP_ROOT_DEPTH):
    """回傳 (apps, errors)。/Applications 本身讀不到時 errors 會有內容。

    library：None = 預設 ~/Library；傳空字串 "" 則不掃 ~/Library。
    """
    roots = roots or DEFAULT_ROOTS
    library = LIBRARY if library is None else library
    apps, errors = [], []
    for root, source in roots:
        _walk(root, source, depth, apps, errors, top=True)
    if library:
        _scan_library(library, apps)
    return apps, errors


def _key(app):
    return app.get("bundle_id") or app.get("path")


def update(out_dir=None, roots=None, now=None, library=None):
    """掃描並更新清冊。回傳 dict：{"status", "removed", "added", "count", "message"}。"""
    out_dir = out_dir or os.path.dirname(os.path.abspath(__file__))
    now = (now or datetime.now(TAIPEI)).isoformat(timespec="seconds")
    inv_path = os.path.join(out_dir, INVENTORY)
    chg_path = os.path.join(out_dir, CHANGES)

    apps, errors = scan(roots, library)
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

    prev_scope = (prev or {}).get("scope", 1)
    scope_changed = prev is not None and prev_scope != SCOPE_VERSION
    newly_listed = []
    if scope_changed:
        # 範圍擴大後才看得到的 App 早就裝著，不算新安裝
        newly_listed, added = added, []

    lines = []
    if prev is None:
        lines.append({"date": now, "change": "baseline", "count": len(apps)})
    if scope_changed:
        lines.append({"date": now, "change": "scope_change", "from": prev_scope,
                      "to": SCOPE_VERSION, "count": len(apps),
                      "newly_listed": len(newly_listed)})
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
        json.dump({"generated_at": now, "scope": SCOPE_VERSION, "count": len(apps),
                   "apps": apps}, f, ensure_ascii=False, indent=2)
    os.replace(tmp, inv_path)

    parts = []
    if removed:
        parts.append("已移除：" + "、".join(a["name"] for a in removed))
    if added:
        parts.append("新安裝：" + "、".join(a["name"] for a in added))
    if prev is None:
        msg = f"已建立 App 清冊基準（{len(apps)} 個 App）"
    elif scope_changed:
        msg = (f"App 清冊掃描範圍已擴大（第 {SCOPE_VERSION} 版），"
               f"新列入 {len(newly_listed)} 個原本就裝著的 App，共 {len(apps)} 個")
        if parts:
            msg += "｜" + "；".join(parts)
    elif parts:
        msg = "App 清冊有變動｜" + "；".join(parts)
    else:
        msg = f"App 清冊無變動（{len(apps)} 個 App）"
    return {"status": "ok", "removed": removed, "added": added,
            "count": len(apps), "message": msg}


if __name__ == "__main__":
    result = update()
    print(result["message"])
    sys.exit(0 if result["status"] == "ok" else 1)
