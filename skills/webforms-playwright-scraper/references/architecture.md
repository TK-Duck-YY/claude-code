# 模組模板

## config.py

```python
# config.py — 目標系統選擇器設定（唯一需要依系統調整的檔案）

BASE_URL = "https://your-system/Homepage.aspx"
SEARCH_URL_TEMPLATE = "https://your-system/Common/TspIndexSearch.aspx?keyword={keyword}"

# 登入偵測
LOGIN_PAGE_URL_KEYWORD    = "Login"
LOGIN_SUCCESS_URL_KEYWORD = "Homepage"

# 搜尋結果 GridView
RESULT_GRID_ID           = "ctl00_ContentPlaceHolder1_gridDetail"
RESULT_ROW_CLASS         = "GridItemS"
PAGER_POSTBACK_TARGET    = "ctl00$ContentPlaceHolder1$gridDetail"

# 行為設定
LOGIN_TIMEOUT_SECONDS    = 300
PAGE_LOAD_TIMEOUT_MS     = 30_000
DETAIL_PAGE_DELAY_SECONDS = 0.8
```

---

## browser.py

```python
# browser.py — 瀏覽器啟動與登入等待

import time
from playwright.sync_api import Playwright, Browser, Page
import config


def launch_browser(playwright: Playwright) -> tuple[Browser, Page]:
    browser = playwright.chromium.launch(
        channel="chrome",
        headless=False,
        args=["--start-maximized"],
    )
    context = browser.new_context(no_viewport=True)
    page = context.new_page()
    return browser, page


def navigate_to_site(page: Page) -> None:
    page.goto(config.BASE_URL, wait_until="domcontentloaded",
              timeout=config.PAGE_LOAD_TIMEOUT_MS)


def wait_for_login(page: Page) -> None:
    print(f"[登入] 請在瀏覽器中手動登入，完成後程式自動繼續。")
    print(f"[登入] 等待中（最多 {config.LOGIN_TIMEOUT_SECONDS} 秒）…")
    deadline = time.time() + config.LOGIN_TIMEOUT_SECONDS
    while time.time() < deadline:
        url = page.url
        if config.LOGIN_SUCCESS_URL_KEYWORD in url:
            print("[登入] 登入成功！")
            return
        if config.LOGIN_PAGE_URL_KEYWORD not in url:
            print("[登入] 登入成功（URL 已離開登入頁）！")
            return
        time.sleep(1)
    raise TimeoutError("登入等待超時。")
```

---

## local_export.py

```python
# local_export.py — Excel / CSV 匯出

import csv
from datetime import datetime
from pathlib import Path
from scraper import FormRecord


def _default_path(keyword: str, ext: str) -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_kw = keyword.replace("/", "_").replace("\\", "_")[:20]
    return str(Path.home() / "Desktop" / f"搜尋_{safe_kw}_{ts}.{ext}")


# 依實際需要的欄位調整
COLUMNS = [
    "#", "表單類型", "表單編號", "申請者", "申請者部門", "申請日期",
    "修配事項", "底價單項目", "說明", "金額", "廠商名稱", "目前狀態", "核准日期",
]


def _row_data(rec: FormRecord) -> list:
    d = rec.merged
    return [rec.index] + [d.get(c, "") for c in COLUMNS[1:]]


def export_excel(records: list[FormRecord], keyword: str) -> str:
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("[Excel] 請執行：pip install openpyxl")
        return ""

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "搜尋結果"

    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(color="FFFFFF", bold=True, size=11)

    for ci, col in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=ci, value=col)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{ws.cell(1, len(COLUMNS)).coordinate}"

    for rec in records:
        ws.append(_row_data(rec))
        if rec.index % 2 == 0:
            fill = PatternFill("solid", fgColor="D9E1F2")
            for ci in range(1, len(COLUMNS) + 1):
                ws.cell(row=rec.index + 1, column=ci).fill = fill

    path = _default_path(keyword, "xlsx")
    wb.save(path)
    return path


def export_csv(records: list[FormRecord], keyword: str) -> str:
    path = _default_path(keyword, "csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        for rec in records:
            writer.writerow(_row_data(rec))
    return path
```

---

## main.py（互動式主流程）

```python
# main.py

import sys
from playwright.sync_api import sync_playwright
import browser as br, scraper, local_export


def ask(prompt, default=""):
    hint = f"（預設：{default}）" if default else ""
    try:
        value = input(f"{prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n[中斷]")
        sys.exit(0)
    return value if value else default


def ask_int(prompt, default, min_val=1, max_val=9999):
    while True:
        raw = ask(prompt, str(default))
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
        except ValueError:
            pass
        print(f"  請輸入 {min_val}～{max_val} 的整數。")


def ask_choice(prompt, choices, default):
    opts = "/".join(choices)
    while True:
        raw = ask(f"{prompt} [{opts}]", default).lower()
        if raw in [c.lower() for c in choices]:
            return raw
        print(f"  請輸入 {opts} 之一。")


def main():
    print("=" * 60)
    print("  搜尋自動化工具")
    print("=" * 60)

    with sync_playwright() as pw:
        browser, page = br.launch_browser(pw)
        try:
            br.navigate_to_site(page)
            br.wait_for_login(page)

            while True:
                print("\n" + "─" * 60)
                keyword = ask("搜尋關鍵字")
                if not keyword:
                    print("  關鍵字不可為空。")
                    continue

                max_records = ask_int("最多擷取幾筆", default=5)
                mode = ask_choice("呈現模式（簡列/詳述）", ["簡列", "詳述"], "詳述")
                fetch_detail = (mode == "詳述")

                try:
                    scraper.execute_search(page, keyword)
                    records = scraper.collect_records(page, max_records, fetch_detail)
                except Exception as e:
                    print(f"\n[錯誤] {e}")
                    if ask_choice("\n繼續？", ["y", "n"], "n") == "n":
                        break
                    continue

                if not records:
                    print("  未找到結果。")
                    if ask_choice("\n繼續？", ["y", "n"], "n") == "n":
                        break
                    continue

                # 顯示結果（依系統調整 output.py）

                export = ask_choice("匯出格式？", ["xlsx", "csv", "n"], "xlsx")
                if export == "xlsx":
                    path = local_export.export_excel(records, keyword)
                    if path:
                        print(f"\n[匯出] 已儲存：{path}")
                elif export == "csv":
                    path = local_export.export_csv(records, keyword)
                    if path:
                        print(f"\n[匯出] 已儲存：{path}")

                if ask_choice("\n繼續搜尋？", ["y", "n"], "n") == "n":
                    break

        finally:
            print("\n[結束] 關閉瀏覽器。")
            browser.close()


if __name__ == "__main__":
    main()
```

---

## 啟動.command（macOS 雙擊啟動）

```bash
#!/bin/bash
cd "$(dirname "$0")"
source .venv/bin/activate
python main.py
```

記得 `chmod +x 啟動.command`。

---

## 依賴安裝

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install playwright openpyxl
playwright install chromium
```
