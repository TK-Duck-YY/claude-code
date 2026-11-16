---
name: "mac-health-check"
description: "當使用者說電腦（M1 MacBook Pro 2020, 8GB 統一記憶體）變頓、風扇很吵、想清電腦、查資源佔用、清硬碟垃圾、清快取、硬碟空間突然變少、查 CPU/記憶體、清除已刪除 App 的殘留檔案與權限設定、或想做完整健康檢查時使用；取代 mac-resource-cleanup。"
---

## 背景與定位

這是使用者自己的合併版 skill，取代兩個原本觸發詞高度重疊的 skill：`mac-resource-cleanup`（Anthropic 內建，用 computer-use 操作螢幕）與 `desktop-commander:computer-health-check`（Desktop Commander 外掛）。

**2026-11-16 決策：移除 Desktop Commander 外掛，本 skill 不再依賴它。**
- 原因：它靠 `npx`（Node.js）啟動，這台 Mac 沒裝 Node.js，至少從 2026-11-05 起每次都啟動失敗（`Failed to spawn process: No such file or directory`）。健檢與清殘留用 computer-use＋device_bash 已能完成；真的需要在 Mac 上跑終端機指令時，使用者已有 Claude Code（`~/.local`，不需要 Node.js）。
- 否決：安裝 Node.js 保留外掛（多一套執行環境，外掛又標示「無需詢問即可執行程式碼」，不符精實目標）；用 Homebrew 裝 Node.js（要先多裝一套 Homebrew）。

使用者的機器：M1 MacBook Pro 2020，8GB 統一記憶體，時區 Taipei，全程用**繁體中文**回報，簡潔直接，不套用制式報告格式（除非資訊量大到非用列點不可）。使用者的目標是「電腦內的程式與設定越精實越好」。

## Step 0：工具分工與流程

- **computer-use 背景工具（`computer_app_*`）**：看與操作活動監視器、系統設定、系統資訊、Finder；Path C 保護區的刪除也靠它。限制：Terminal 是 click 層級，不能打字；瀏覽器唯讀。
- **device_bash**：在 Linux 虛擬機裡讀寫使用者授權的資料夾（`~/Library` 等），適合用 `ls`、`du`、`rm` 掃描與刪除殘留。**不能**執行 macOS 指令（`pmset`、`system_profiler`、`mo`、`brew` 都跑不了），也看不到 `/Applications`。
- **使用者自己在 Terminal（或 Claude Code）執行**：只有 macOS 指令才拿得到的數據、mo、brew。我列出完整指令讓他複製貼上，再解讀他貼回的結果。不要嘗試用 computer-use 在 Terminal 打字。

流程：第一部分 CPU／記憶體 → 第二部分 硬碟 → 第三部分 電池與維護 → 評分回報 → 完整健檢時一併做 Path C 的殘留盤點。使用者只要清殘留時直接走 Path C。

開始前用 `computer_resolve_access` → `computer_request_access` 一次申請活動監視器、系統設定、Finder（第三部分需要時再加「系統資訊」）。使用者偏好背景模式：一律用 `computer_app_*`，不拿整個螢幕。

---

## 第一部分：CPU / 記憶體（活動監視器）

1. `computer_open_application` 開啟（背景啟動），用 `computer_app_screenshot` 取得畫面。
2. CPU 分頁：依「% CPU」遞減排序（欄位標題點一次可能是遞增，再點一次）。記下視窗下方的閒置率（Idle）。
3. 點右上搜尋框再輸入 `claude`，檢查是否有大量小寫 `claude`（不是 `Claude` 或 `Claude Helper`）背景程序：
   - 正常：`Claude`（主程式）、`Claude Helper` 系列、`Claude Helper (Renderer)` 系列、`Virtual Machine Service for Claude`、`Claude的...` 都是 App 正常運作的必要程序，絕對不要結束它們。
   - 異常：十幾二十個以上的小寫 `claude` 程序，且「CPU 時間」累積 10 小時以上，代表過去的 Claude Code / Cowork 背景工作階段沒有正常關閉。這是已知會發生的狀況，不是使用者操作錯誤。
   - 清除搜尋：點搜尋框右邊的 ⓧ。背景模式下用打字覆蓋或刪除會失敗。
4. 記憶體分頁：記下「記憶體壓力」顏色（綠/黃/紅）與「使用的交換空間」，作為前後對照。交換空間偏高時，依記憶體排序列出前幾名（常見：`Virtual Machine Service for Claude`、`Claude Helper (Renderer)`、Safari／Chrome 的網頁分頁），建議關掉不用的分頁；重開機最有效。
5. 清除異常殘留：點第一個小寫 `claude` 資料列，按住 Shift 點最後一個（注意不要選到 `Claude` / `Claude Helper` 相關列），點工具列左上角停止圖示，核對彈出清單裡全部都是單純 `claude`、沒有夾帶 `Claude` / `Claude Helper` / `Claude的...`，再點「結束」。一次選取失敗就改成一次處理少量、每次操作後截圖確認，避免快速連續點擊同一座標被誤判為雙擊。
6. 清完後回報：記憶體壓力顏色變化、交換空間變化、目前殘留的 claude 程序數量（正常應只剩 0–1 個，對應使用者正在用的工作階段）。

## 第二部分：硬碟空間

1. 系統設定：`computer_app_menu` 走「View → General」，點「Storage」。剛打開會顯示「Calculating…」，等幾秒再截一次圖。記下總容量、已用、可用與各分類（應用程式、macOS、系統資料等），判斷哪些是正常佔用。
2. Finder：`computer_app_menu` 走「Go → Library」開啟資源庫（Go 選單的固定項目在背景可用；**不要用「前往檔案夾」**，見文末「背景操作的已知限制」）。切成列表檢視，點「Size」欄位標題由大到小排序，點資料夾左邊的展開三角形看第二層，依序看：
   - `Metadata`（Spotlight 索引）：正常約 1–2 GB。2026-11-05 與 11-16 兩次都膨脹到約 46 GB，主要在底下的 `DocumentProcessing`。超過 10 GB 就回報，處理方式由使用者決定。
   - `Application Support`、`Containers`、`Group Containers`（OneDrive、Dropbox 等雲端同步軟體常在這裡堆積本機快取）、`Caches`、`CloudStorage`。
   - Downloads 用「Go → Downloads」。
   看到已刪除 App 的資料夾時，記下來交給 Path C。
3. `~/Library/Application Support/Claude`（約 15 GB，含 vm_bundles）是 Cowork / Claude Code 沙盒環境的核心，不是垃圾，絕對不要建議刪除。
4. OneDrive 本機快取異常肥大時：
   - 不要用 `request_access` 開 OneDrive App（系統辨識不到這個 App 名稱）。
   - 指導使用者自己操作：選單列 OneDrive 雲朵圖示 →「...」→「設定」→「同步與備份」→「進階」→「檔案隨選 (建議)」裡的「釋出空間」。安全、可逆（檔案還在雲端），背景處理要幾分鐘到幾十分鐘，提醒使用者之後回頭確認可用空間。
   - 不要建議使用者手動進 Group Containers 刪東西，會弄壞 OneDrive 同步資料庫。

## 第三部分：電池與維護

1. 系統設定左側「Battery」：記下「Battery Health」（Normal 為正常）與充電上限。最大容量可點 Battery Health 旁的 ⓘ 查看（這一步尚未實測，取不到就標「沒取得」）。
2. 系統設定「General → Software Update」：看有沒有待裝的系統／安全性更新。
3. 「系統資訊」App：硬體 → 電源 看「循環計數」；儲存裝置 看「S.M.A.R.T. 狀態」。這條路尚未實測，第一次使用時確認欄位位置，取不到就標「這項沒取得」。
4. 開機天數在畫面上看不到。需要時請使用者在 Terminal 跑 `uptime` 貼回；不跑就該項不計分。

---

## 評分規則

每項評 🟢 良好 / 🟡 留意 / 🔴 需處理，總分從 100 起算，每個 🟡 扣 8 分、每個 🔴 扣 18 分，下限 0 分。90+ 優秀、75–89 良好、60–74 普通、<60 需要處理。**沒取得的項目不計分**，回報時註明哪幾項沒計分。

| 項目 | 🟢 良好 | 🟡 留意 | 🔴 需處理 |
|---|---|---|---|
| 可用硬碟空間 | 剩餘 >20% | 10–20% | <10% |
| 硬碟健康 (SMART) | Verified/OK | — | 異常 |
| 記憶體壓力 | 低 swap、壓力綠色 | 有感 swap（幾百 MB 以上）/壓縮 | 大量 swap、壓力黃紅 |
| 電池 | 最大容量 ≥80%、Normal | 70–80% | <70% 或需要服務 |
| 維護 | 開機 <7 天、無待處理更新 | 7–30 天或小更新 | >30 天或安全性更新待裝 |
| 開機項目 | 第三方項目少 | 中等 | 第三方常駐程式很多 |
| 即時資源 | 閒置時沒有 >50% 的程序 | 一個持續偏高 | 多個/失控程序 |

開機項目看 Finder 裡的 `~/Library/LaunchAgents`（展開三角形）；屬於已刪除 App 的項目列入 Path C。

## 回報格式

```
🖥️  健康檢查 — <型號>，<系統版本>     分數：<N>/100（<評語>）

🟢/🟡/🔴  儲存空間  — 可用 <X> / 總共 <Y>（<%>）。可回收約 <Z> GB
🟢/🟡/🔴  記憶體    — <一句話狀態>
🟢/🟡/🔴  電池      — <循環次數> 次，最大容量 <%>，<狀態>
🟢/🟡/🔴  維護      — 開機 <天數> 天，<更新狀態>
🟢/🟡/🔴  開機項目  — <數量> 個第三方項目（<列出幾個>）
🟢/🟡/🔴  即時狀態  — 最高：<程序> <cpu%>、<程序> <cpu%>

建議（依效益排序，最多列 3–5 項）
1. ...
```

## 建議規則（發現 → 建議）

- **開機超過 30 天** → 建議重啟（清記憶體、套用待處理更新），投入最小、效益最高，排在建議第一項。
- **有待處理的系統／安全性更新** → 提醒安裝；安全性更新優先於一般更新。
- **剩餘空間 <15%** → 先列出實測最大的幾個佔用項目。
- **Downloads／Caches／垃圾桶很大** → 垃圾桶請使用者自己清空；Downloads 列出最大的幾個檔名讓使用者判斷；可重建的快取列出路徑與大小。
- **使用者貼回的 `brew outdated` 很多或快取很大** → 列出 `brew upgrade`、`brew cleanup` 給使用者自己執行。
- **電池最大容量 <80%** → 說明損耗屬正常現象；若已影響續航才考慮送修。
- **第三方開機項目多** → 點名列出，建議使用者到「系統設定 → 一般 → 登入項目」停用不需要的，不要直接修改檔案。
- **閒置時有程序持續高 CPU** → 點名該程序，建議結束或進一步查原因。
- **發現已刪除 App 的殘留（檔案、LaunchAgents、隱私權限項目）** → 進入 Path C。

## 清理流程

1. 收集階段全程唯讀，先回報結果與建議，不主動動手清理。
2. 每項建議若對應具體指令，**先把完整指令顯示給使用者**。
3. 分三類處理：
   - **使用者同意後我可執行**：Path C 中使用者已確認的已刪除 App 殘留；結束確認過的殘留小寫 `claude` 程序。
   - **只列清單與指令，由使用者自己執行**：清空垃圾桶、刪除快取資料夾或使用者檔案、刪除 Downloads 內檔案、停用登入項目、安裝系統更新、解除安裝仍在使用的 App、移除隱私權限項目、處理 Spotlight 索引暫存、所有 `brew` 與 `mo` 指令。
   - **絕對不做**：sudo／提權、刪除系統檔案、磁碟或分割區操作。
4. 執行後回報實際變化（例如釋出多少空間），並重新檢查一次確認。

## 數據原則

- 一律實測，不憑印象填數字。不得捏造容量、循環次數、狀態。取不到就直接說「這項沒取得」，不要用推測補上。
- 標明數字來源：活動監視器、系統設定、Finder，或使用者貼回的 Terminal／mo 輸出。
- 程序與檔案清單限制筆數（`head` 等），避免洗版。

## 選配：請使用者在 Terminal 執行的指令

只在使用者想補齊畫面上拿不到的數據時提供（全部唯讀，bash 與 zsh 都能跑）：

```
uptime; pmset -g batt | head -n 2; system_profiler SPPowerDataType 2>/dev/null | grep -Ei "Cycle Count|Condition|Maximum Capacity"; diskutil info / | grep -i SMART
```

判讀：`Maximum Capacity` 是耗損指標，`Condition: Normal` 是好的，出現「Service Recommended」是 🔴；SMART 顯示 `Verified` 才算健康，其他一律 🔴。

**mo（mole，github.com/tw93/mole）**：只有使用者自己提到 mo/mole 時才用。請他自己跑預覽指令並把結果貼回：`mo status`、`mo analyze`、`mo clean --dry-run`、`mo uninstall --dry-run`、`mo purge --dry-run`、`mo installer --dry-run`。真正會刪除或改動系統的指令（`mo clean`、`mo uninstall`、`mo purge`、`mo installer`、`mo optimize`、`mo remove`）只列出來讓使用者自己決定要不要執行。使用者沒裝 mo 就不主動推薦。

---

## Path C：已刪除 App 的殘留檔案與權限清理

使用者刪掉 App 後，常留下設定檔、快取、登入憑證、背景服務（LaunchAgents）與隱私權限項目。健康檢查時主動列出這類殘留；使用者要求清殘留時走這條路。

### C0. 先讀 App 清冊（2026-11-16 起）

使用者的「App更新檢查」程式（`~/Documents/Claude/App更新檢查`，有排程自動執行）每次執行都會透過 `app_inventory.py` 產出：
- `inventory.json`：已安裝的 App（`/Applications`、`/System/Applications`、`~/Applications` 與往下一層），每筆有 `name`、`bundle_id`、`version`、`path`、`app_store`，另有 `generated_at`。
- `inventory_changes.jsonl`：累積的變動紀錄，一行一筆，`change` 為 `baseline`／`removed`／`added`，只增不刪。

每次走 Path C（或完整健檢）時：
1. 申請該資料夾的存取權（唯讀），讀這兩個檔。檔案不存在代表排程還沒跑過新版，請使用者先執行一次「檢查App更新.app」。
2. `generated_at` 超過 7 天代表排程可能沒在跑，提醒使用者。
3. **已移除的 App**：取 `change` = `removed` 的項目（之後又出現同一 `bundle_id` 的 `added` 代表重新安裝，跳過），用 `bundle_id` 與廠商前綴去 C2 掃描殘留。同一筆紀錄下次還會出現，掃不到殘留就回報「已清乾淨」。
4. **全面盤點（補充）**：把 `~/Library` 各子資料夾（Application Support、Containers、Group Containers、Preferences、Caches、HTTPStorages、LaunchAgents 等）裡的名稱，對照 `inventory.json` 的 `bundle_id` 與廠商前綴，找不到主人的列為「疑似殘留」。`com.apple.*` 與系統項目、C1 的共用資料、Path C 禁區略過。**「疑似殘留」一律列清單請使用者確認，不自動刪。**
5. **清冊有盲點（2026-11-16 實測）**：它只掃到應用程式資料夾往下一層，所以裝在更深處的 App（例如 `應用程式/Autodesk/AutoCAD 2026/`）和裝在其他位置的元件（例如中華電信憑證元件 CHTSCTokenApp 裝在 `~/Library/HiPKILocalSignServer`）都不在清冊上。**「清冊上沒有」只是線索，不是證據**，每一組都要過 C1 的安裝檢查。
6. 不要修改這兩個檔案，它們由程式管理。

### C1. 判斷擁有者是否還在用

**主判斷＝系統查得到有沒有安裝；輔助＝清冊與「App更新檢查」保護名單。** 任一顯示「有在用」就保留。

1. **安裝檢查（主，列清單前每一組都要做）**：
   - `computer_list_apps`，`query` 傳廠商關鍵字或 bundle id 片段（例如 `autodesk`、`chttl`、`dropbox`）。它列出系統登記的 App，不管裝在哪裡，也不需要授權（2026-11-16 用它找到 `~/Library` 裡的 CHTSCTokenApp）。
   - `computer_resolve_access` 傳 App 名稱（可一次傳多個寫法）：回到 `notInstalled` 代表沒裝，**但要看 `didYouMean`**——出現相近名稱（例如問「AutoCAD」回「AutoCAD 2026」）代表其實有裝。
   - 教訓：2026-11-16 曾只看清冊，把仍在使用的 AutoCAD 2026 支援資料（`Application Support/Autodesk` 692 MB）列成殘留，使用者追問才發現。
   - 名稱不確定時，用 Finder 開「應用程式」核對；另外檢查 `~/Applications`（使用者自製的 `改寫.app`、`翻譯.app` 在這裡）。
2. **保護名單（輔）**：讀 `App更新檢查/results.json` 的 `rows[].name`，名單上的 App 一律保留。這份清單只涵蓋「查得到更新來源」的 App，**不在清單上不等於沒用**：macOS 內建 App、沒有更新來源的 App、終端機工具（Claude Code、mole）都不在清單上，但不能當殘留。
3. **殘留名稱對應擁有者**：用 bundle id 的廠商前綴判斷，例如 `com.openai.*`／`ChatGPTHelper`／`Codex` → ChatGPT、Codex；`ai.perplexity.*`／`CometUpdater` → Perplexity、Comet；`com.google.GeminiMacOS*`／`group.com.google.gemini` → Gemini；`com.google.drivefs*` → Google Drive；`com.microsoft.m365copilot`／`*.com.microsoft.copilot.*` → Copilot；`tw.com.chttl.*`／`HiPKI*` → 中華電信憑證元件。同一廠商可能有多個產品（Perplexity App 與 Comet 瀏覽器），每個都要確認。
4. **同廠商的共用資料一律保留**：名稱含 `common`、`shared`、`Office` 等、由同廠商多個產品共用的資料夾（例如 `group.com.google.common` 是 Chrome 與 Google Drive 共用；Microsoft Office 的共用容器），只要該廠商還有任何產品在用就不動。`Application Support/Google` 底下只有 `DriveFS` 屬於 Google Drive，`Chrome`、`GoogleUpdater`、`RLZ` 屬於 Chrome。
5. 同一個資料夾可能被多個產品共用（例如 `~/.codex` 同時是 ChatGPT 桌面版的 Codex 功能與 Codex CLI 的設定目錄），要確認使用者全部都不用。
6. **終端機工具的設定資料夾**（家目錄下的 `~/.gemini`、`~/.codex` 等）常不屬於桌面 App，而是 CLI 或其他程式（例如 Grok Bot 派工給 Gemini）在用。檢查修改時間，最近仍在寫入就先告訴使用者、預設保留；使用者同意刪除時一律**移到垃圾桶、不永久刪除**，提醒觀察一兩天，確定沒有程式出錯再清空；若出錯就從垃圾桶放回原處。
7. **元件本體不在應用程式資料夾時**（例如 `~/Library/HiPKILocalSignServer/CHTSCTokenApp.app`），使用者選擇整套移除，就把整個廠商資料夾移到垃圾桶，再清 Containers 的殘殼。
8. 被問到「這是不是程式本體」時：`Application Support`、`Containers` 等是 App 的資料（授權、登入、設定、範本、快取），本體在「應用程式」或廠商自訂的位置；App 還在時刪資料，輕則要重新登入或啟用授權，重則 App 打不開。

### C2. 掃描（device_bash，唯讀）

1. 用 `device_request_folder_access` 申請 `~/Library`、`~/Applications`（需要時加 `~/.<app>`）。申請前用一句話說明：**這只是授權我讀寫這些「已存在」的資料夾，不會建立任何新資料夾或檔案，授權只在本次對話有效**（2026-11-16 使用者曾誤以為會多建資料夾而拒絕）。
2. 用廠商前綴與 App 名稱搜尋，範圍：`Preferences`、`HTTPStorages`、`WebKit`、`Caches`、`Logs`、`Sounds`、`Application Scripts`、`Saved Application State`、`Containers`、`Group Containers`，用 `du -sh` 附大小。
3. device_bash 看不到或刪不掉的位置（Permission denied / Operation not permitted）改用 Finder：`Application Support`、`LaunchAgents`、`Cookies`，以及 `Containers`、`Group Containers` 裡帶 `.com.apple.containermanagerd.metadata.plist` 的資料夾——這兩類即使取得刪除授權，device_bash 仍是 `Operation not permitted`。
4. **大小以 Finder 為準**：`Containers`、`Group Containers` 內部受 macOS 保護，device_bash 的 `du` 會嚴重低估（實例：Microsoft 365 Copilot 容器 du 顯示 48K，Finder 實際 1.99 GB）。列清單時這兩類標注「大小待 Finder 確認」。
5. **Finder 顯示名稱 ≠ 資料夾名稱**：`Containers` 在 Finder 顯示的是 App 顯示名稱（例如 `tw.com.chttl.CHTSCToken` 顯示為「CHTSCTokenApp」、`com.microsoft.m365copilot` 顯示為「Microsoft 365 Copilot」、`com.google.GeminiMacOS.WidgetExtension` 顯示為「Gemini」）。用 bundle id 找不到時改用 App 名稱找，並核對路徑列。

### C3. 列清單 → 使用者確認

用 AskUserQuestion 或分組清單一次列出：每組的擁有者、安裝檢查結果、位置與大小、建議（可刪／要你確認／不動）、刪除方式（永久刪除不能復原／移到垃圾桶）。含登入憑證（如 `auth.json`）要點名；終端機工具的設定資料夾單獨列一組。使用者對某個 App 說「照同樣方式清掉」時視為同意，但仍要先做 C1 的安裝檢查。

### C4. 刪除

- **一般位置**（Preferences、WebKit、HTTPStorages、Application Scripts 等）：`device_request_delete_permission`（只列需要的資料夾根目錄）→ device_bash `rm -rf` 逐項刪除，每項回報 DELETED／FAILED／MISSING → 再搜一次確認歸零。
- **保護區**（Application Support、Containers、Group Containers）——**背景方法，2026-11-16 實測可行，優先使用**：
  1. `computer_app_menu` 走「Go → Library」。
  2. 依需要點「Name」或「Size」欄位排序；點資料夾左邊的展開三角形（優先用 `element_index`）。Containers 有一千多項，展開後等右下角轉圈消失再截圖。Group Containers 裡以 `.app` 結尾的項目會顯示成種類「Application」、不顯示副檔名。
  3. 用 `computer_app_scroll` 捲到目標列，點那一列的**日期欄位附近**讓它選取（不要點名稱文字，以免進入改名）。
  4. 用 `computer_app_zoom` 放大視窗底部路徑列，確認是 `Library › <上層> › <目標>` 且名稱完全相符。
  5. `computer_app_menu` 走「File → Move to Trash」。**一次一項**；刪完重新截圖再找下一項（列表會上移，原座標會變成下一個項目）。
  6. File 選單沒有「Move to Trash」（只看到 Put Back、Quick Look "Trash"）代表垃圾桶視窗變成主視窗：回 Library 視窗重新點一次目標列，選單就會恢復。
  7. **不要用 `shift+down` 多選鄰近項目**：相鄰的不一定是同一家（2026-11-16 選 Gemini 容器時，下一列是 OneDrive 的 `FinderSync`，差點一起刪掉）。
- **全螢幕控制（備案）**：背景方法走不通時才用 `computer_request_full_control`。此時可用「Go → Go to Folder…」→ `cmd+A` 清空 → 輸入路徑 → Return；每次導覽後先截圖確認視窗標題是目標資料夾。不要用 `cmd+shift+G`（隱私權面板開著時會搶走焦點）、`cmd+shift+H` 等導覽快速鍵（曾跳到「應用程式」並選中 Adobe Acrobat）。選取後用 zoom 核對名稱與路徑列，再按 `cmd+backspace`。家目錄的隱藏資料夾用 `cmd+shift+.` 顯示，處理完再隱藏。完成後 `computer_release_full_control`。
- **Finder 操作禁忌**：不要憑座標盲點標題列或工具列附近（2026-11-16 曾誤點「新增檔案夾」，在「應用程式」多建一個 untitled folder）；點之前先截圖確認位置，選到非目標項目時絕不能刪除。
- 外接螢幕：截圖看不到視窗時用 `computer_switch_display`；系統設定可能跳到最前面，先點 Dock 的 Finder 圖示再操作。
- 完成後用 device_bash 再搜一次確認歸零，提醒使用者觀察一兩天、確認常用 App 正常後再自己清空垃圾桶。

### C5. 隱私權限（系統設定 → 隱私權與安全性）

- computer-use 無法操作「Privacy & Security」面板內部（`com.apple.settings.PrivacySecurity.extension` 解析不到），移除項目又需要管理員密碼或 Touch ID。**這部分一律交給使用者**：系統設定左上搜尋框輸入「Full Disk Access」→ 點項目名稱讓整列反白（不要點開關）→ 按清單最下方左邊的「−」（看不到就捲到清單底部）→ Touch ID／密碼確認。
- 確認灰色項目還在不在：右鍵 →「Show in Finder」，Finder 沒反應或打不開就代表原檔已不在。
- 刪掉 App 後，macOS 有時會自動移除它的權限項目（2026-11-16 刪除 Codex Computer Use 後就自動消失），先截圖確認再請使用者動手。
- 要檢查的分類：完全取用磁碟、輔助使用、螢幕與系統錄音、自動化、輸入監控。
- 開關為「關」的項目沒有任何權限，移除只是讓清單乾淨；開關為「開」的未知項目才有安全意義（例如 `bash` 開著完全取用磁碟，代表任何 bash 腳本都能讀寫整顆硬碟，要提醒使用者確認用途）。

### 權限清單「同名雙生」判讀
- `applet`：用工作指令碼編輯程式／Automator 做的小程式，執行檔一律叫 applet，所以不同小程式會同名（例如使用者的「檢查App更新.app」）。
- 小寫 `claude` 是 Claude Code 指令列程式，大寫 `Claude` 是桌面 App，兩者不同、不能當重複刪。
- 黑色 exec 圖示＝指令列執行檔；灰色格狀圖示＝沒有圖示或原檔已找不到。

### Path C 禁區
- `~/Library/Application Support/Claude`（含 vm_bundles）、`Claude-3p`、`~/.claude`、`~/.local`（Claude Code）、`~/.grokbot` 與 `grok-bot-computer-use`、使用者自製的 `com.<user>.*`（`~/Applications/改寫.app`、`翻譯.app`、`com.<user>.appupdatecheck.plist`、`~/Documents/Claude/App更新檢查`）一律不動。
- 仍在使用的 App 的資料（例如 AutoCAD 2026 的 `com.autodesk.*`、`Application Support/Autodesk`、`AdSSO-v2`）與仍在使用的廠商的共用資料不動。
- 不確定屬於哪個 App 的項目只列出、不刪。

---

## 背景操作的已知限制（2026-11-16 實測）

- Finder「前往檔案夾」對話框：背景模式可以輸入路徑，但送不出 Return，也送不出 Esc，只能按對話框右邊的關閉鈕（可能要按兩次）。背景模式下不要用它，改用 Go 選單的固定項目＋展開三角形。
- 活動監視器搜尋框：可以點一下再輸入；清除要按 ⓧ。
- 使用者停在全螢幕 App 的畫面時，Finder 在背景不回應點擊（讀不到視窗），也無法把視窗移過來，只有捲動有效。這時請使用者切回一般桌面再說「繼續」，或照截圖指引自己操作。
- 中斷很久（例如兩小時）回來時，App 的操作授權可能已失效，要重新 `computer_resolve_access` → `computer_request_access`。

## 安全界線（全部適用）

- **絕對不要**自己清空垃圾桶，或在使用者確認清單前刪除任何檔案。唯一例外是 Path C：使用者確認清單後，已刪除 App 的殘留可以由我刪除（一般位置永久刪除、保護區與終端機工具設定資料夾移到垃圾桶）。使用者自己的文件、Downloads、快取資料夾仍只列清單、由使用者動手。
- **絕對不要**使用 sudo 或任何需要提權的指令。
- 輸入密碼、Touch ID 驗證一律由使用者自己做。
- 結束背景程序（如異常殘留的小寫 `claude` CLI 程序）不算刪除資料，可以直接執行，但僅限確認過是單純殘留程序、不是使用者正在用的工作階段或 App 核心程序時才動手。
- 若無法判斷某個項目是垃圾還是正在使用中的資料，回報給使用者讓他自己決定，不要自作主張。
- 收集階段全程唯讀。清理一律依上方「清理流程」三分類處理。本節與「清理流程」若有出入，以本節第一條為準。

## 回報格式（總則）

用繁體中文，簡潔直接，不要套用制式條列報告格式，除非資訊量大到非用列點不可。清楚講：發現了什麼、佔多少空間/資源、判斷是不是垃圾、建議怎麼處理、由誰執行（我或使用者）。數字標明來源（活動監視器、系統設定、Finder，或使用者貼回的 Terminal／mo 輸出），避免使用者搞混來源。