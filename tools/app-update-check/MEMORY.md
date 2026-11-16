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
