---
name: "hotel-search"
description: "查詢 Amex FHR（Fine Hotels + Resorts）和 IHG One Rewards 飯店的即時房價與會員福利摘要。只要使用者提到旅遊計劃、查飯店、訂房、FHR、IHG、Fine Hotels、Amex 飯店、會員福利、查房價、hotel、accommodation、想住哪裡、出國住宿等關鍵字，或問某城市有哪些會員優惠飯店，就立即啟動此 Skill。不需要使用者明確說「hotel-search」——只要意圖是查飯店價格或會員福利，就使用。"
---

# 飯店會員福利即時查詢

透過 Claude 的**內建瀏覽器**（Claude desktop app 內的瀏覽器面板，工具名稱 `mcp__remote-devices__Claude_Browser__*`）操作 Amex 和 IHG 網頁，掃描 FHR 和/或 IHG One Rewards 飯店的即時房價與會員福利，並在對話中以表格呈現結果。

為什麼用內建瀏覽器：它有獨立且**持續保存的設定檔**，Amex / IHG 登入一次後，之後的對話通常仍維持登入狀態，不必每次重登；且與使用者自己的 Chrome 隔離，不會干擾其正在使用的分頁。

## 開始前 — 載入工具

內建瀏覽器工具若為 deferred，用**一次** ToolSearch 全部載入：
`ToolSearch { query: "mcp__remote-devices__Claude_Browser__", max_results: 64 }`

若內建瀏覽器工具不存在或呼叫連不上（desktop app 關閉或離線），告知使用者「內建瀏覽器目前離線」，並詢問是否改用 Claude in Chrome；**等使用者同意後**才切換（改用 `mcp__claude-in-chrome__*` 對應工具，操作步驟相同）。不要自行切換，因為那會在使用者真正的 Chrome 裡操作。

## 流程

### Q1 — 入住日期
直接請使用者輸入入住和退房日期（純文字，不用選單）：
> 「請輸入入住 / 退房日期（例：10/31 – 11/1）」

### Q2 — 地區
用 `AskUserQuestion` 選單（multiSelect: false）：
- 日本
- 東南亞
- 歐洲
- 美洲
（Other 讓使用者自由輸入）

### Q3 — 城市或飯店
用 `AskUserQuestion` 選單（multiSelect: false）：
- 指定城市（Other 輸入城市名）
- 指定飯店名稱（Other 輸入飯店名）

> 若答案是「指定飯店名稱」，跳過 Q4，直接進 S5。
> 指定飯店不可能同時在 FHR 和 IHG，不需問查哪個系統。

### Q4 — 查詢系統
用 `AskUserQuestion` 選單（multiSelect: false）：
- Amex FHR
- IHG One Rewards
- 兩者都查

### S5 — 開啟網站並確認登入狀態

1. 用 `preview_start`（帶 `url`）開啟對應網站，一次呼叫即開新分頁並回傳 `tabId`，記下每個網站的 `tabId`：
   - **FHR** → `https://www.amextravel.com`
   - **IHG** → `https://www.ihg.com/hotels/us/en/reservation`

   兩者都查時各開一個分頁。

2. **先檢查是否已登入**（內建瀏覽器會保留先前的登入）：用 `get_page_text` 或 `find` 檢查頁面：
   - 出現會員姓名、點數餘額、「Sign Out / Log Out」、「My Account」→ 已登入，**直接進 S6**，不必打擾使用者
   - 出現「Sign In / Log In」按鈕或登入表單 → 未登入，進第 3 步

3. **請使用者登入**（僅未登入的網站）：
   - 先呼叫 `tabs_context`，看結果結尾的瀏覽器面板狀態：
     - **not open**：先用 `preview_start` 開頁面，再檢查一次
     - **hidden**：先請使用者把瀏覽器叫回來：「請按 Cmd+Shift+B（或關閉側邊面板中的其他內容後點地球圖示）顯示瀏覽器面板」
     - **displayed**：可直接進行
   - 告知使用者：「請在右側瀏覽器面板中登入 [Amex / IHG]，登入後回覆『好了』」
   - 使用者回覆後再檢查一次登入狀態，確認成功才進 S6

使用者已存在的登入是他本人的帳號：不要登出、不要改帳號設定，只做查詢所需的操作。

### S6 — 掃描並顯示結果

使用內建瀏覽器工具在已登入頁面操作搜尋，每次呼叫都帶上該網站的 `tabId`（分頁 ID 每次不同，不要硬編碼；不確定時用 `tabs_context` 重新取得）。
讀取頁面優先用 `get_page_text` / `read_page`（取得實際文字與結構），只有需要看版面時才用 `computer` 截圖。
使用者可隨時輸入「停止」中止掃描，此時停下並顯示目前已掃到的結果。

若某網站被拒絕存取或需要授權，依工具提示呼叫 `request_access`（scope 用 "site"），等使用者回覆後再重試；被拒絕就告知使用者並跳過該網站。

---

#### FHR 掃描步驟

1. **目的地輸入**：
   - `computer` `triple_click` 清除目的地欄 → `type` 輸入城市名
   - 等 autocomplete 下拉出現 → `left_click` 第一個建議
   - Amex Travel 是 SPA，URL 參數無效，必須透過表單操作

2. **日期**：設定入住/退房日期

3. **FHR filter**（最重要的步驟）：
   - 先用 `find` 取得「Apply Filters」按鈕的 ref
   - 再用一次 `browser_batch`：click FHR checkbox → 立刻 click Apply Filters
   - 中間**不能滾動頁面**，否則 React 會重設 checkbox 狀態
   - FHR checkbox 是 React 元件，必須用 `left_click`（`form_input` 對 React checkbox 無效）

4. **讀取結果**：`get_page_text` 擷取飯店名稱、房價、福利標籤（如 $100 credit、5X points）

---

#### IHG 掃描步驟

1. **目的地**：click 目的地欄 → `type` 城市名 → 等 autocomplete → click 第一個建議

2. **日期**：
   - click Check-in 欄位開啟日曆
   - 日曆從當月開始，按 `>` 翻月到目標月份
   - click 入住日 → click 退房日

3. **搜尋**：click SEARCH → 等待 3 秒 → 確認結果載入（等到「X Hotels Found」出現）

4. **讀取結果**：擷取飯店名稱、品牌、距離、TWD 房價

**注意**：帶查詢參數的直接 URL 會被 Akamai 阻擋，必須用表單操作。

---

#### 結果格式（在對話中以表格顯示）

使用者可能沒在看瀏覽器面板，所以所有結果都要完整寫在對話中。

**🏅 Amex FHR 結果：**
| 飯店 | 房價/晚 | 總計（含稅） | 會員福利 |
|------|---------|------------|---------|
| 飯店名稱 | USD xxx | USD xxx | $100 現場消費額度、5倍MR點數… |

**🏨 IHG One Rewards 結果：**
| 飯店 | 品牌 | 距離 | 房價/晚（TWD） | 備註 |
|------|------|------|--------------|------|
| 飯店名稱 | Crowne Plaza | 0.38 km | 7,290 TWD | 僅剩少量 |

> **IHG Platinum Elite 通用福利**（每間適用，搜尋頁不顯示）：優先升等、歡迎禮、延遲退房至 16:00、加碼點數

---

### Q7 — 後續
用 `AskUserQuestion` 選單（multiSelect: false）：
- 重新查詢（回到 Q1）
- 前往訂房（提供飯店的訂房頁連結）
- 結束

## 重要技術提醒

- **登入狀態會保留**：內建瀏覽器設定檔跨對話保存，S5 一律先檢查登入，已登入就跳過；登入逾期（網站自動登出）時才請使用者重登
- **Tab ID 每次都不同**：以 `preview_start` 回傳的 `tabId` 為準，遺失時用 `tabs_context` 取得，不要硬編碼
- **請使用者操作前先確認面板可見**：用 `tabs_context` 檢查，面板隱藏時先請使用者按 Cmd+Shift+B
- **兩者都查時**：先掃 FHR、再掃 IHG，最後一起呈現完整比較結果
- **IHG 搜尋半徑**：預設 30 英里範圍，距離太遠的飯店（>10km）建議在備註欄標注
- **內建瀏覽器離線時**：詢問使用者是否改用 Claude in Chrome，得到同意才切換