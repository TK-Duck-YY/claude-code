# MEMORY.md

## 2026-11-16：新增完整 App 清冊（app_inventory.py），供 mac-health-check 清殘留

**決定：** 讓 check_updates.py 每次執行時順便呼叫 app_inventory.py，產出：
- `inventory.json`：/Applications、/System/Applications、~/Applications（含一層子資料夾）裡所有 App 的名稱、識別碼（bundle id）、版本、路徑、是否 App Store。每次覆寫。
- `inventory_changes.jsonl`：累積的「新增／移除」紀錄，只增不刪。第一次執行寫一行 baseline。

**為什麼：** mac-health-check 原本只能在使用者「點名」刪了哪個 App 後才去找殘留。
results.json 每次被覆寫、只含查得到更新來源的 App、也沒有識別碼，無法比對新舊。
有了累積紀錄，就算兩次健檢之間隔很久、中間跑過很多次排程，移除紀錄也不會遺失。

**設計要點：**
- 清冊失敗只印提示，不影響更新檢查（update_inventory() 包 try/except）。
- 掃到 0 個 App，或數量少於上次一半 → 不覆寫、不記變動（防止排程被權限擋住時把全部 App 誤判為移除）。
  副作用：若真的一次刪掉超過一半的 App，清冊會停在舊版，需手動執行 `python3 app_inventory.py` 前先確認。
- 版本升級、換位置不算變動。
- `sys.dont_write_bytecode = True`，避免在專案資料夾產生 __pycache__。

**否決的做法：**
- B：由 mac-health-check 自己存清冊 → 只在健檢時記錄，兩次健檢之間裝了又刪的 App 會漏。
- C：只做全面盤點、不比新舊 → 每次從頭判斷，慢且誤判多（仍保留作為補充，抓基準建立之前就刪掉的 App）。

## 2026-11-16：擴大清冊掃描範圍（SCOPE_VERSION 2）

**決定：** 採方案 C——
- 三個應用程式資料夾從「往下一層」改成「往下三層」（不進入 .app 內部、不跟隨捷徑）。
- 另外掃 `~/Library` 每個資料夾的第一層 `.app`，`LIBRARY_SKIP` 清單裡的資料夾不進去：其他 App 的資料容器（Containers、Group Containers 等）、個人資料與受保護資料夾（Mail、Messages、Safari 等）、雲端與快取（CloudStorage、Caches、Metadata 等）。
- `inventory.json` 加上 `scope` 欄位。範圍改變的第一次執行，新看到的 App 不記成「新增」，只寫一行 `scope_change`（含 `newly_listed` 數量）；「移除」照常記錄。

**為什麼：** 健檢時清冊漏掉兩個仍在使用的 App，差點被當成殘留刪掉：
- AutoCAD 2026：裝在 `/Applications/Autodesk/AutoCAD 2026/`，第兩層以下。
- 中華電信憑證元件 CHTSCTokenApp：裝在 `~/Library/HiPKILocalSignServer/`，不在應用程式資料夾。

**否決的做法：**
- A：只加深應用程式資料夾的層數 → 抓不到裝在 `~/Library` 的元件。
- B：改用 Spotlight（`mdfind`）找全機 App → 依賴 Spotlight 索引（這台的索引曾兩次膨脹到約 46 GB）；結果混雜垃圾桶、外接磁碟與 App 內部小程式，要另寫過濾；排程背景執行的行為未實測。

**實測（2026-11-16 19:58，使用者手動執行「檢查App更新.app」）：** 沒有跳出任何 macOS 權限詢問；清冊 96 → 99 個，寫入一行 `scope_change`（`newly_listed` 3：AutoCAD 2026、AutoCAD Plot Style Editor 2026、Remove AutoCAD 2026）；`~/Library` 第一層 0 個（中華電信元件已移除）；無「移除」紀錄、無 `__pycache__`。日後若排程跳出權限詢問，把該資料夾名稱加進 `LIBRARY_SKIP`。

**測試：** 模擬資料夾測試 6 項全過（第三層 App 有列入、第四層與 .app 內部不列入、`~/Library` 第一層有列入、跳過清單有效、範圍變更不算新增、數量驟減時不覆寫）。
