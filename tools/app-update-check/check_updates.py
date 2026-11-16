#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
check_updates.py — 統一查詢 Mac 上各 app 是否有新版
涵蓋來源：
  1. Google Chrome        → Google 官方 VersionHistory API
  3. Microsoft 全系列     → 內建 msupdate 命令列工具（Microsoft AutoUpdate 附帶）
  4. AnyDesk              → Homebrew 版本資料庫 API（可能延遲數日）
  5. Garmin Express       → Homebrew 版本資料庫 API（可能延遲數日）
  6. Mac App Store 全部   → Apple iTunes Lookup API（自動掃描含 _MASReceipt 的 app）

只查詢、不安裝。所有查詢並行執行，全程只用 Python 標準函式庫。

每次執行也會呼叫 app_inventory.py，更新完整 App 清冊（inventory.json）與
累積的新增／移除紀錄（inventory_changes.jsonl），供 mac-health-check 清殘留用。
"""

import json
import os
import plistlib
import re
import ssl
import subprocess
import sys
import unicodedata
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta

APPLICATIONS = "/Applications"
MSUPDATE = ("/Library/Application Support/Microsoft/MAU2.0/"
            "Microsoft AutoUpdate.app/Contents/MacOS/msupdate")
TIMEOUT = 20  # 每個網路請求的秒數上限

# 終端機色彩（非 tty 時自動關閉）
_TTY = sys.stdout.isatty()
def _c(code, s):
    return f"\033[{code}m{s}\033[0m" if _TTY else s
RED = lambda s: _c("31;1", s)
GREEN = lambda s: _c("32", s)
YELLOW = lambda s: _c("33;1", s)
DIM = lambda s: _c("2", s)


# ---------------------------------------------------------------- 工具函式

def http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {})
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
        return r.read().decode("utf-8", errors="replace")


def local_version(app_path, key="CFBundleShortVersionString"):
    """讀取 app 的 Info.plist 版本號；app 不存在回傳 None。

    多數 app 用 CFBundleShortVersionString，但少數（少數 app 如此）
    這個欄位只寫大版號「7.3」，真正可比對的完整版號在 CFBundleVersion，
    這種情況由 key 參數指定。
    """
    plist = os.path.join(app_path, "Contents", "Info.plist")
    try:
        with open(plist, "rb") as f:
            return plistlib.load(f).get(key)
    except (FileNotFoundError, NotADirectoryError):
        return None


def ver_tuple(v):
    """'150.0.7871.129' → (150, 0, 7871, 129)；非數字段落忽略。"""
    return tuple(int(x) for x in re.findall(r"\d+", v or ""))


def compare(local, remote):
    """比較版本，回傳狀態字串。

    'update' 來源版本較新 → 有新版可更新
    'ok'     兩者相同 → 已是最新
    'stale'  來源版本比本機還舊 → 來源資料已過期，這次查詢「無法確認」。
             絕不能當成「最新」——來源都追不上本機了，自然也不會知道
             有沒有更新的版本存在（2026-07-24 AnyDesk 實例：brew 停在
             9.7.1、本機 9.7.2、官方其實已出 9.7.3，卻被誤報成最新）。
    """
    lt, rt = ver_tuple(local), ver_tuple(remote)
    if not lt or not rt:
        return "unknown"
    # 段數不同時補零比較（7.29.1.0 vs 7.29.1 視為相同）
    n = max(len(lt), len(rt))
    lt += (0,) * (n - len(lt))
    rt += (0,) * (n - len(rt))
    if rt > lt:
        return "update"
    if rt < lt:
        return "stale"
    return "ok"


# ---------------------------------------------------------------- 各來源查詢
# 每個 checker 回傳 list[dict]：
#   {name, local, remote, status, note}
#   status: ok / update / unknown（查詢失敗）

def check_chrome():
    name = "Google Chrome"
    local = local_version(f"{APPLICATIONS}/Google Chrome.app")
    if not local:
        return []
    # Chrome 採「分階段推送」：新版先放給少數人，數天內才擴大到 100%。
    # Chrome 內建更新器只會拿到「已輪到這台機器」的版本，所以這裡不能直接把
    # 全球最高版號當成「該更新」——那會對還在 0.5% 試裝的版本誤報。
    # 做法：只有推送比例達到門檻（多數人已可裝）的版本才算「正式最新版」；
    # 更高但仍在小量推送的版本，僅以附註提示「分階段推送中」，不標紅。
    ROLLOUT_THRESHOLD = 0.5  # 50%，超過才視為廣泛可用
    try:
        raw = http_get("https://versionhistory.googleapis.com/v1/chrome/"
                       "platforms/mac/channels/stable/versions/all/releases"
                       "?filter=endtime=none")
        releases = json.loads(raw).get("releases", [])
        # 同一版號可能有多筆，取各版號的最大推送比例
        frac = {}
        for r in releases:
            v = r["version"]
            frac[v] = max(frac.get(v, 0), r.get("fraction", 1))
        if not frac:
            raise ValueError("無發布資料")

        broad = [v for v, f in frac.items() if f >= ROLLOUT_THRESHOLD]
        mainstream = max(broad or frac, key=ver_tuple)  # 廣泛可用的最高版
        highest = max(frac, key=ver_tuple)              # 全球最高（可能小量推送）

        note = "Google 官方 API"
        if ver_tuple(highest) > ver_tuple(mainstream):
            pct = frac[highest] * 100
            note += f"；{highest} 分階段推送中 {pct:.1f}%，尚未輪到你"

        st = compare(local, mainstream)
        if st == "stale":
            # 本機版本比「已廣泛推送版」新，代表被分到早期推送群組，屬正常，
            # 不是來源過期（Chrome 的來源是官方 API，不會過期）
            st = "ok"
        return [dict(name=name, local=local, remote=mainstream,
                     status=st, note=note)]
    except Exception as e:
        return [dict(name=name, local=local, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


def check_sketchup():
    """SketchUp 裝在 /Applications/SketchUp 2026/ 子資料夾內（不是最上層）。
    本機 CFBundleVersion 是 26.2.242，Homebrew cask 寫成 2026.2.242.76（年份用四位數、
    多一段 build），格式不同，必須轉換後才能比對。"""
    name = "SketchUp 2026"
    local = local_version(f"{APPLICATIONS}/SketchUp 2026/SketchUp.app",
                          "CFBundleVersion")
    if not local:
        return []
    try:
        raw = http_get("https://formulae.brew.sh/api/cask/sketchup.json",
                       headers={"User-Agent": "curl/8.0"})
        parts = json.loads(raw)["version"].split(",")[0].split(".")
        if len(parts[0]) == 4:
            parts[0] = str(int(parts[0]) - 2000)
        if int(parts[0]) != ver_tuple(local)[0]:
            return [dict(name=name, local=local, remote=".".join(parts),
                         status="ok", note=f"Homebrew 已是 {parts[0]} 年度版（另購），"
                         "本機這個年度版沒有可查的新版")]
        remote = ".".join(parts[:len(ver_tuple(local))])
        return [dict(name=name, local=local, remote=remote,
                     status=compare(local, remote),
                     note="Homebrew 資料庫（可能延遲數日）")]
    except Exception as e:
        return [dict(name=name, local=local, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


def check_mole():
    """Mole（終端機工具 mo）：不是 .app，沒有 Info.plist。本機版本讀 `mo --version`，
    最新版查 GitHub 官方 Release（比 Homebrew 即時；tag 帶大寫 V 前綴，如 V1.57.0）。
    排程由 launchd 執行，PATH 只有 /usr/bin:/bin 等，找不到 /usr/local/bin，必須用絕對路徑。"""
    name = "Mole（終端機工具）"
    mo = "/usr/local/bin/mo"
    if not os.path.exists(mo):
        return []
    try:
        out = subprocess.run([mo, "--version"], capture_output=True,
                             text=True, timeout=15).stdout
        m = re.search(r"Mole version\s+(\d[\d.]*)", out)
        if not m:
            raise ValueError("讀不到本機版本")
        local = m.group(1)
    except Exception as e:
        return [dict(name=name, local=None, remote=None,
                     status="unknown", note=f"讀取本機版本失敗：{e}")]
    try:
        raw = http_get("https://api.github.com/repos/tw93/Mole/releases/latest",
                       headers={"User-Agent": "curl/8.0"})
        remote = json.loads(raw)["tag_name"].lstrip("vV")
        return [dict(name=name, local=local, remote=remote,
                     status=compare(local, remote), note="GitHub 官方 Release")]
    except Exception as e:
        return [dict(name=name, local=local, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


def check_grokbot():
    """Grok Bot（Cursor 公司出品的 Electron app，Squirrel 更新）：沒有 Homebrew cask、
    不在 App Store。查 app 內建的更新 API：
    https://api2.cursor.sh/updates/api/update/darwin-arm64/sand/<本機版本>/<任意值>/stable
    已是最新 → HTTP 204（無內容）；有新版 → JSON {"url":..., "name":"新版本"}。
    （非官方公開文件，是從 app 內讀出的端點；格式改了會變成 unknown。）"""
    name = "Grok Bot"
    app = os.path.join(APPLICATIONS, "Grok Bot.app")
    if not os.path.exists(app):
        return []
    local = local_version(app)
    if not local:
        return [dict(name=name, local=None, remote=None,
                     status="unknown", note="讀取本機版本失敗")]
    url = ("https://api2.cursor.sh/updates/api/update/darwin-arm64/sand/"
           f"{local}/0/stable")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=TIMEOUT,
                                    context=ssl.create_default_context()) as r:
            code, body = r.status, r.read().decode("utf-8", "replace")
        if code == 204 or not body.strip():
            return [dict(name=name, local=local, remote=local, status="ok",
                         note="app 內建更新 API")]
        remote = str(json.loads(body)["name"]).lstrip("vV")
        return [dict(name=name, local=local, remote=remote,
                     status=compare(local, remote), note="app 內建更新 API")]
    except Exception as e:
        return [dict(name=name, local=local, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


def check_microsoft():
    """msupdate --list：一列代表全部 Microsoft app（MAU 管理範圍）。"""
    name = "Microsoft 全系列（MAU）"
    if not os.path.exists(MSUPDATE):
        return [dict(name=name, local=None, remote=None,
                     status="unknown", note="找不到 msupdate 工具")]
    try:
        out = subprocess.run([MSUPDATE, "--list"], capture_output=True,
                             text=True, timeout=120).stdout
        clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]|\[2K", "", out)
        if "No updates available" in clean:
            return [dict(name=name, local="—", remote="—", status="ok",
                         note="Word/Excel/PPT/Outlook/OneNote/Teams/OneDrive")]
        # 有更新時，msupdate 會列出待更新項目
        pending = [l.strip() for l in clean.splitlines()
                   if l.strip() and "Update Assistant" not in l
                   and "Checking" not in l]
        return [dict(name=name, local="—", remote="—", status="update",
                     note="；".join(pending[:6]) or "有可用更新")]
    except Exception as e:
        return [dict(name=name, local=None, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


# 用 Homebrew 版本資料庫查的 app：
#   (顯示名稱, /Applications 下的資料夾名, cask 名[, 版本欄位])
# 之後裝了新的「非 App Store」app，只要在這裡加一行即可。
# cask 名查法：到 https://formulae.brew.sh/cask/ 搜尋 app 名稱。
# 第 4 元素（版本欄位）可省略，預設 CFBundleShortVersionString；
# 若某 app 該欄位只寫大版號（只寫大版號如「7.3」），改填 "CFBundleVersion"。
BREW_CASK_APPS = [
    ("AnyDesk", "AnyDesk.app", "anydesk"),
    ("Garmin Express", "Garmin Express.app", "garmin-express"),
    ("Claude", "Claude.app", "claude"),
    ("Sena 藍牙裝置管理", "SenaDeviceManager.app", "senadevicemanager"),
    ("Adobe Acrobat Pro", "Adobe Acrobat DC/Adobe Acrobat.app", "adobe-acrobat-pro"),
    # OneDrive 不在這裡查——它其實註冊在 Microsoft AutoUpdate 管理範圍內
    # （msupdate --config 可看到 /Applications/OneDrive.app，Application ID
    # ONDR18），已經被 check_microsoft()／「Microsoft 全系列（MAU）」那行
    # 覆蓋，且 MAU 是官方即時資料源，比這裡常常延遲的 Homebrew cask 資料庫
    # 可靠得多。2026-08-14 移除，見 MEMORY.md 同日記錄。
]


def _check_brew_cask(name, app_dir, cask, key="CFBundleShortVersionString"):
    local = local_version(f"{APPLICATIONS}/{app_dir}", key)
    if not local:
        return []
    try:
        raw = http_get(f"https://formulae.brew.sh/api/cask/{cask}.json",
                       headers={"User-Agent": "curl/8.0"})
        remote = json.loads(raw)["version"].split(",")[0]
        return [dict(name=name, local=local, remote=remote,
                     status=compare(local, remote),
                     note="Homebrew 資料庫（可能延遲數日）")]
    except Exception as e:
        return [dict(name=name, local=local, remote=None,
                     status="unknown", note=f"查詢失敗：{e}")]


def check_brew_apps():
    rows = []
    for entry in BREW_CASK_APPS:
        rows.extend(_check_brew_cask(*entry))
    return rows


def _mas_apps():
    """掃描 /Applications 中含 App Store 收據的 app。

    收據必須是非空檔案：真正的 App Store 收據含加密內容（數 KB），
    0 bytes 的空收據是仿冒的（曾遇過非 App Store 來源的 app 帶假收據）。
    """
    apps = []
    for entry in sorted(os.listdir(APPLICATIONS)):
        if not entry.endswith(".app"):
            continue
        path = os.path.join(APPLICATIONS, entry)
        receipt = os.path.join(path, "Contents", "_MASReceipt", "receipt")
        try:
            if os.path.getsize(receipt) == 0:
                continue
        except OSError:
            continue
        plist = os.path.join(path, "Contents", "Info.plist")
        try:
            with open(plist, "rb") as f:
                info = plistlib.load(f)
            apps.append((entry[:-4], info.get("CFBundleIdentifier"),
                         info.get("CFBundleShortVersionString")))
        except Exception:
            continue
    return apps


def _lookup_mas(display, bundle_id, local):
    # entity=desktopSoftware：部分 app（如 NordVPN）在 App Store 是 iOS/macOS
    # 通用上架，預設查詢會回傳 iOS 版本號（版號序列跟 macOS 版完全不同，
    # 例：NordVPN iOS 側 9.9.0 vs macOS 側 10.6.0），必須指定 desktopSoftware
    # 才能拿到跟本機安裝版本同一序列的號碼（2026-07-27 驗證：其餘既有 app
    # 加這個參數後結果不變，不會造成回歸）。
    for country in ("tw", "us"):
        try:
            raw = http_get(f"https://itunes.apple.com/lookup"
                           f"?bundleId={bundle_id}&country={country}"
                           f"&entity=desktopSoftware",
                           headers={"User-Agent": "curl/8.0"})
            results = json.loads(raw).get("results", [])
            if results:
                remote = results[0].get("version")
                return dict(name=f"{display}（App Store）", local=local,
                            remote=remote, status=compare(local, remote),
                            note="")
        except Exception:
            continue
    return dict(name=f"{display}（App Store）", local=local, remote=None,
                status="unknown", note="App Store 查無資料")


def check_mas():
    apps = _mas_apps()
    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(lambda a: _lookup_mas(*a), apps))


# ---------------------------------------------------------------- 主流程

CHECKERS = [check_chrome, check_sketchup, check_mole, check_grokbot, check_microsoft,
            check_brew_apps, check_mas]

ICON = {"ok": GREEN("✅ 最新"), "update": RED("⚠️  有新版"),
        "stale": YELLOW("❓ 無法確認"), "unknown": YELLOW("❓ 查不到")}


def disp_width(s):
    """終端機顯示寬度：全形（中文等）算 2 格。"""
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in s)


def pad(s, width):
    return s + " " * max(0, width - disp_width(s))


def update_inventory():
    """順便更新完整 App 清冊（app_inventory.py）。

    清冊給 mac-health-check skill 判斷哪些 App 已被移除、要清殘留。
    任何錯誤都只印提示，絕不影響下面的更新檢查。
    """
    try:
        sys.dont_write_bytecode = True  # 不在專案資料夾產生 __pycache__
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import app_inventory
        result = app_inventory.update()
        print(DIM(result["message"]))
    except Exception as e:
        print(DIM(f"（App 清冊更新失敗，不影響更新檢查：{e}）"))


def main():
    update_inventory()
    print(DIM("查詢中（各來源並行，最慢的是 Microsoft msupdate，約 10–30 秒）…"))
    rows = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        for result in pool.map(lambda f: f(), CHECKERS):
            rows.extend(result)

    # 有新版排最前，其次是無法確認的（需人工看一眼），已最新殿後
    order = {"update": 0, "stale": 1, "unknown": 2, "ok": 3}
    rows.sort(key=lambda r: order.get(r["status"], 4))

    w_name = max(disp_width(r["name"]) for r in rows) + 2
    print()
    print(pad("App", w_name) + pad("目前版本", 17) + pad("最新版本", 17) + "狀態")
    print("─" * (w_name + 46))
    for r in rows:
        loc = r["local"] or "—"
        rem = r["remote"] or "—"
        line = pad(r["name"], w_name) + pad(loc, 17) + pad(rem, 17) + ICON[r["status"]]
        if r["note"]:
            line += DIM(f"  {r['note']}")
        print(line)

    n_upd = sum(1 for r in rows if r["status"] == "update")
    n_stale = sum(1 for r in rows if r["status"] == "stale")
    n_unk = sum(1 for r in rows if r["status"] == "unknown")
    print()
    if n_upd:
        print(RED(f"共 {n_upd} 個 app 有新版可更新。"))
        print(DIM("更新方式：Chrome → app 內「關於」頁；Microsoft → "
                  "Microsoft AutoUpdate；App Store app → App Store「更新」頁；Mole → 終端機執行 mo update；"
                  "Claude → 結束後重開會自動更新；AnyDesk/Garmin → 官網下載。"))
    else:
        print(GREEN("所有能確認的 app 都已是最新版。"))
    if n_stale:
        print(YELLOW(f"{n_stale} 個 app 無法確認：查詢來源的版本比你本機的還舊，"
                     "代表來源資料已過期。"))
        print(DIM("  這種情況請以 app 自己的更新提示為準（AnyDesk 會在主畫面"
                  "顯示橘色更新通知）。"))
    if n_unk:
        print(YELLOW(f"{n_unk} 個項目查詢失敗（網路或來源問題），可稍後重試。"))

    if "--json" in sys.argv or os.environ.get("CHECK_UPDATES_JSON"):
        out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "results.json")
        taipei = timezone(timedelta(hours=8))
        payload = {
            "checked_at": datetime.now(taipei).isoformat(),
            "rows": rows,
        }
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
        print(DIM(f"\n結構化結果已寫入：{out_path}"))


if __name__ == "__main__":
    main()
