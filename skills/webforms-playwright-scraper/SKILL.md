---
name: "webforms-playwright-scraper"
description: "Build a Playwright-based scraper for ASP.NET WebForms internal systems — especially systems with GridView search results, PostBack pagination, iframe overlay detail pages, and approval workflow tables. Use this skill whenever the user wants to automate search or data extraction from a WebForms ERP, OA, or approval system, or asks to build a Playwright scraper for a legacy enterprise web system. Also use when the user has an existing scraper hitting common WebForms pitfalls (iframe not scanned, locators stale after PostBack, GridView pager broken, label matching wrong table headers, missing body-text search results)."
---

# ASP.NET WebForms × Playwright 搜尋自動化

這份 skill 記錄了在真實 ASP.NET WebForms 企業系統中完成 Playwright 搜尋自動化的架構
與關鍵技術模式。遇到同類需求時直接套用，避免重複踩坑。

## 專案架構

```
scraper-project/
├── config.py          # URL 與 CSS/XPath selector（唯一需要依系統調整的地方）
├── browser.py         # 瀏覽器啟動、手動登入等待
├── scraper.py         # 搜尋、擷取、詳細頁核心邏輯
├── output.py          # 終端機輸出（簡列/詳述）
├── local_export.py    # Excel (.xlsx) / CSV 匯出
├── main.py            # 互動式主流程
└── 啟動.command       # macOS 雙擊啟動腳本
```

讀取 `references/architecture.md` 取得各模組的完整模板程式碼。  
讀取 `references/patterns.md` 取得關鍵技術難點的解決方案與程式碼片段。

## 瀏覽器使用分工

這個 skill 會碰到兩種「瀏覽器」，用途不同，不要混用：

### A. Claude 自己要看網頁時 → 預設用內建瀏覽器

探查目標系統（找 GridView ID、row class、PostBack target、iframe 結構）、驗證 selector、
查 Playwright 文件等，一律先用**內建瀏覽器**（`mcp__remote-devices__Claude_Browser__*`）。
只有使用者明確說要用 Chrome / Claude in Chrome 時，才改用 `mcp__claude-in-chrome__*`。

原因：使用者的偏好瀏覽器設定為內建瀏覽器；它有獨立且持久的 profile，登入狀態會保留，
使用者也能在側邊面板即時看到並接手 SSO / CAPTCHA 登入。

操作要點：
- 工具若為延遲載入，一次全部載入：ToolSearch query `mcp__remote-devices__Claude_Browser__`，max_results 64
- 已知網址用 `preview_start` 直接開新分頁；讀結構用 `read_page` / `get_page_text`，
  截圖只在版面本身是重點時使用
- 需要使用者手動登入前，先呼叫 `tabs_context` 確認面板狀態；若面板隱藏，
  請使用者按 Cmd+Shift+B 叫出瀏覽器，再說明要做什麼
- 用 `javascript_tool` 一次取得 config.py 需要的線索：

```js
(() => {
  const grids = [...document.querySelectorAll('table[id*="grid" i]')].map(t => ({
    id: t.id,
    rowClasses: [...new Set([...t.querySelectorAll('tr')].map(r => r.className).filter(Boolean))]
  }));
  const postbacks = [...document.querySelectorAll('a[href*="__doPostBack"]')]
    .slice(0, 10).map(a => a.getAttribute('href'));
  const iframes = [...document.querySelectorAll('iframe')].map(f => ({ id: f.id, src: f.src }));
  return { url: location.href, grids, postbacks, iframes };
})()
```

- 若內建瀏覽器因內網 / VPN 限制打不開目標系統，直接告知使用者，改請他提供頁面 HTML
  或截圖；不要未經同意自行切換到 Chrome
- 內建瀏覽器離線（桌面 App 未開啟）時，告知使用者並詢問是否改用 Chrome，等回覆再動作

### B. 產出的 Playwright 程式執行時 → 維持本機 Chrome

`browser.py` 的 `playwright.chromium.launch(channel="chrome")` 不變，由使用者在 Mac 本機執行。
內建瀏覽器無法被 Playwright 驅動，也不共用登入 Cookie，所以探查結果只用來填 config.py，
不要嘗試讓爬蟲程式連到內建瀏覽器。

## 實作順序

1. **先填 config.py** — 用內建瀏覽器探查（見上節 A），把目標系統的 URL、GridView ID、行 class 填進去；其他模組依賴它
2. **建 browser.py** — launch Chrome，等待使用者手動登入（企業系統通常有 SSO/CAPTCHA）
3. **實作 scraper.py** — 搜尋 → 雙來源擷取 → 詳細頁 → 簽核表解析
4. **加 local_export.py** — openpyxl Excel 匯出
5. **串 main.py** — 互動式迴圈

## 五個最常見的 WebForms 陷阱

### 陷阱 1：搜尋輸入框找不到 / timeout
**原因**：ASP.NET UpdatePanel 的非同步載入，input 在 DOM 中但尚未可互動。  
**解法**：直接 `page.goto(SEARCH_URL_TEMPLATE.format(keyword=...))` 繞過首頁 input，
讓搜尋 URL 帶 keyword 參數導航到結果頁。

### 陷阱 2：GridView 只有「標題欄位命中」，漏掉「內文命中」記錄
**原因**：WebForms 全文搜尋頁通常有兩個區域：
- 上方全文搜尋區塊（所有關鍵字命中，含內文）
- 下方 GridView（只有標題欄位命中）  

若只讀 GridView，會系統性遺漏內文命中的記錄。  
**解法**：雙來源合併，見 `references/patterns.md` § 雙來源搜尋。

### 陷阱 3：點擊詳細頁後 iframe 內容擷取不到
**原因**：`page.locator("td")` 不掃 iframe；詳細頁常以 iframe overlay 呈現。  
**解法**：偵測 `len(page.frames)` 變化，在所有 `page.frames` 掃描，見 §iframe 偵測。

### 陷阱 4：標籤掃描誤命中表格欄標題
**原因**：簽核表、底價單的欄標題（如「簽核時間」）被當成 label，
下一格是「簽核狀態」→ 寫入錯誤值。  
**解法**：表格型資料用 XPath `normalize-space(text())` 專門函式處理，
不放進通用 DETAIL_LABELS；見 §表格解析。

### 陷阱 5：`locator.all()` 搭配 PostBack 後 locator 錯位
**原因**：PostBack 後 DOM 重繪，`row_locators[i]` 的 `i` 若因跳過記錄而偏移，
會點到錯誤的列。  
**解法**：`_extract_current_page()` 同時回傳 `(dict, locator)` tuple，
讓 locator 永遠和 row data 配對，不靠 index 對應。

## 核心資料流

```
execute_search(keyword)
    └─ page.goto(SEARCH_URL)
          └─ collect_records(max, fetch_detail)
                ├─ _extract_current_page()        # 雙來源合併
                │     ├─ GridView tr.GridItemS     # 來源一
                │     └─ page.locator("a").all()   # 來源二（全文區）
                ├─ [去重 by 表單編號]
                ├─ _fetch_detail_via_locator()     # 點擊詳細頁
                │     ├─ iframe overlay 偵測
                │     ├─ new tab 偵測
                │     └─ URL change 偵測
                ├─ _extract_label_values()         # 掃描所有 frame
                │     ├─ _scan_texts_for_labels()  # 標籤→值 / 同格解析
                │     ├─ _extract_base_price_items() # 項目表格
                │     └─ _extract_approval_date()  # 簽核流程表
                └─ sort by 申請日期 DESC
```