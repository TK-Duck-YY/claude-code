---
name: "mac-health-check"
description: "當使用者說電腦（M1 MacBook Pro 2020, 8GB 統一記憶體）變頓、風扇很吵、想清電腦、查資源佔用、清硬碟垃圾、清快取、硬碟空間突然變少、查 CPU/記憶體、清除已刪除 App 的殘留檔案與權限設定、或想做完整健康檢查時使用；取代 mac-resource-cleanup 與 desktop-commander:computer-health-check。"
---

## 背景與定位

這是使用者自己的合併版 skill，取代兩個原本各自獨立、觸發詞高度重疊的 skill：
1. `mac-resource-cleanup`（Anthropic 內建，用 computer-use 操作螢幕：活動監視器 + Finder + 系統設定）
2. `desktop-commander:computer-health-check`（Desktop Commander 外掛，用它自己的本機終端機唯讀掃描 + 健康評分）

兩者疊在一起時，Claude 常常先選了需要 Desktop Commander 的那個，結果 Desktop Commander 沒連線，卡住還要臨時改用另一條路。這個 skill 把邏輯合一，一開始就先判斷走哪條路，不再讓使用者或 Claude 自己選。

使用者的機器：M1 MacBook Pro 2020，8GB 統一記憶體，時區 Taipei，全程用**繁體中文**回報，簡潔直接，不套用制式報告格式（除非資訊量大到非用列點不可）。使用者的目標是「電腦內的程式與設定越精實越好」。

## Step 0：先判斷走哪條路

檢查 Desktop Commander 的工具（例如 `get_config`、`start_process`）目前在這個 session 裡是否已經連線可用：

- **已連線** → 走 **Path A（Desktop Commander 深度掃描）**，用它現成的唯讀 shell 能力取得更完整的數據（硬碟讀寫、SMART、電池循環次數、風扇/熱狀態、開機項目），並套用底下的評分表格產出健康分數報告。
- **沒連線** → 走 **Path B（computer-use 現場操作）**，用電腦操作工具直接點開活動監視器、Finder、系統設定查。不要嘗試用 computer-use 硬開終端機打字湊合 Desktop Commander 的功能——Terminal 在 computer-use 裡是「click」層級，不能打字，這條路走不通。
- **使用者要清已刪除 App 的殘留** → 走 **Path C**（可與 A/B 並用）。

不確定 Desktop Commander 是否連線時，直接嘗試呼叫一次它的工具；失敗就代表沒連線，直接走 Path B，不要反覆嘗試或卡住使用者。

---

## Path A：Desktop Commander 深度掃描（已連線時使用）

### 收集（唯讀，用 `start_process` 跑，逾時抓 30 秒）

```bash
zsh -c '
echo "== SYSTEM =="; sw_vers; echo "uptime:"; uptime
echo "== HARDWARE =="; system_profiler SPHardwareDataType 2>/dev/null | grep -Ei "Model Name|Chip|Total Number of Cores|Memory:"
echo "== DISK =="; df -h /
diskutil info / 2>/dev/null | grep -Ei "SMART|Free Space"
echo "== MEMORY =="; vm_stat | head -n 8
echo "swap:"; sysctl -n vm.swapusage
echo "== TOP CPU =="; ps -Ao pid,pcpu,pmem,comm -r | head -n 8
echo "== TOP MEM =="; ps -Ao pid,pcpu,pmem,comm -m | head -n 8
echo "== BATTERY =="; pmset -g batt | head -n 2
system_profiler SPPowerDataType 2>/dev/null | grep -Ei "Cycle Count|Condition|Maximum Capacity"
echo "== THERMAL =="; pmset -g therm 2>/dev/null | head -n 3
echo "== STARTUP =="; echo "user agents:"; ls -1 "$HOME/Library/LaunchAgents" 2>/dev/null
echo "service count: $(launchctl list 2>/dev/null | wc -l | tr -d " ")"
echo "== STORAGE HOTSPOTS =="
for d in "$HOME/Downloads" "$HOME/Library/Caches" "$HOME/.Trash" "$HOME/Library/Logs"; do
  [ -d "$d" ] && printf "%s\t%s\n" "$(du -sh "$d" 2>/dev/null | cut -f1)" "${d/#$HOME/~}"
done
echo "== PACKAGES =="
command -v brew >/dev/null 2>&1 && echo "brew outdated: $(brew outdated 2>/dev/null | wc -l | tr -d " "), cache: $(du -sh "$(brew --cache)" 2>/dev/null | cut -f1)" || echo "brew: not installed"
echo "== CRASH REPORTS =="; ls -1 "$HOME/Library/Logs/DiagnosticReports" 2>/dev/null | wc -l
echo "== DONE =="'
```

只跑必要的網路/慢速檢查（`softwareupdate -l`、`networkQuality`）如果使用者有明確問到更新或網速，平常第一輪先跳過。

### 判讀重點

- 記憶體壓力：Apple Silicon 頁面大小 16KB，健康狀態是有足夠 free+inactive 頁面、`vm.swapusage` 的 used 接近 0；用到幾百 MB 以上就是 🟡/🔴。
- 電池：`Maximum Capacity` 是耗損指標，`Condition: Normal` 是好的，出現「Service Recommended」是 🔴。桌機或 `pmset -g batt` 沒回報內建電池就整項跳過。
- SMART：`Verified` 才算健康，其他狀態一律 🔴。
- 開機項目：真正有意義的是 `~/Library/LaunchAgents` 底下列出的第三方項目（更新工具、雲端同步的背景服務等），`launchctl list` 的原始數量大多是系統內建服務，不用特別提。第三方項目屬於已刪除的 App 時，列入 Path C。

### 評分規則

每項評 🟢 良好 / 🟡 留意 / 🔴 需處理，總分從 100 起算，每個 🟡 扣 8 分、每個 🔴 扣 18 分，下限 0 分。90+ 優秀、75–89 良好、60–74 普通、<60 需要處理。

| 項目 | 🟢 良好 | 🟡 留意 | 🔴 需處理 |
|---|---|---|---|
| 可用硬碟空間 | 剩餘 >20% | 10–20% | <10% |
| 硬碟健康 (SMART) | Verified/OK | — | 異常 |
| 記憶體壓力 | 低 swap、free 充足 | 有感 swap/壓縮 | 大量 swap、free 接近 0 |
| 電池 | 最大容量 ≥80%、Normal | 70–80% | <70% 或需要服務 |
| 維護 | 開機 <7 天、無待處理更新 | 7–30 天或小更新 | >30 天或安全性更新待裝 |
| 開機項目 | 第三方項目少 | 中等 | 第三方常駐程式很多 |
| 即時資源 | 閒置時沒有 >50% 的程序 | 一個持續偏高 | 多個/失控程序 |

### 回報格式（Path A）

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
2. ...
```

### 建議規則（發現 → 建議）

- **開機超過 30 天** → 建議重啟（清記憶體、套用待處理更新），投入最小、效益最高，排在建議第一項。
- **有待處理的系統／安全性更新** → 提醒安裝；安全性更新優先於一般更新。
- **剩餘空間 <15%** → 先列出實測最大的幾個佔用項目。
- **Downloads／Caches／垃圾桶很大** → 垃圾桶請使用者自己清空；Downloads 列出最大的幾個檔名讓使用者自己判斷；可重建的快取列出路徑與大小。
- **Homebrew 過期項目多或快取大** → 建議 `brew upgrade` 與 `brew cleanup`。
- **電池最大容量 <80%** → 說明損耗屬正常現象；若已影響續航才考慮送修。
- **第三方開機項目多** → 點名列出，建議使用者到「系統設定 → 一般 → 登入項目」停用不需要的，不要直接修改檔案。
- **閒置時有程序持續高 CPU** → 點名該程序，建議結束或進一步查原因。
- **發現已刪除 App 的殘留（檔案、LaunchAgents、隱私權限項目）** → 進入下方「Path C」。

### 清理流程（Path A 與 Path B 共用）

1. 收集階段全程唯讀，先回報結果與建議，不主動動手清理。
2. 每項建議若對應具體指令，**先把完整指令顯示給使用者**，再詢問是否執行。
3. 分三類處理：
   - **使用者同意後我可執行**：`brew cleanup`（套件管理員的下載快取）；以及 Path C 中使用者已確認的已刪除 App 殘留。
   - **只列清單與指令，由使用者自己執行**：清空垃圾桶、刪除快取資料夾或使用者檔案、刪除 Downloads 內檔案、停用登入項目、安裝系統更新、解除安裝仍在使用的 App、移除隱私權限項目、mo 的破壞性指令。
   - **絕對不做**：sudo／提權、刪除系統檔案、磁碟或分割區操作。
4. 執行後回報實際變化（例如釋出多少空間），並重新跑一次儲存空間檢查確認。

### 數據原則

- 一律實測，不憑印象填數字。不得捏造容量、循環次數、狀態。若某個指令失敗或沒有輸出，直接說明「這項沒取得」，不要用推測補上。
- 程序與檔案清單一律限制輸出筆數（`head` 等），避免洗版。

---

## Path B：computer-use 現場操作（Desktop Commander 沒連線時使用）

### 第一部分：CPU / 記憶體檢查

1. 用 `request_access` 請求「活動監視器」權限，`open_application` 開啟。
2. 切到 CPU 分頁，點兩下「% CPU」欄位標題排序（第一次通常是遞增，需要再點一次變遞減）。
3. 用視窗右上角搜尋框輸入 `claude`，檢查是否有大量小寫 `claude`（不是 `Claude` 或 `Claude Helper`）背景程序：
   - 正常：`Claude`（主程式）、`Claude Helper` 系列、`Claude Helper (Renderer)` 系列、`Claude的...` 都是 App 正常運作的必要程序，絕對不要結束它們。
   - 異常：十幾二十個以上的小寫 `claude` 程序，且「CPU 時間」累積 10 小時以上，代表過去的 Claude Code / Cowork 背景工作階段沒有正常關閉、殘留在背景。這是已知會發生的狀況，不是使用者操作錯誤。
4. 切到「記憶體」分頁，記下「記憶體壓力」顏色（綠/黃/紅）與「使用的交換空間」數值，作為清理前後對照。
5. 清除異常殘留：點第一個小寫 `claude` 資料列，按住 Shift 點最後一個小寫 `claude` 資料列（範圍選取，注意不要選到 `Claude` / `Claude Helper` 相關列），點工具列左上角停止圖示，核對彈出清單裡全部都是單純 `claude`、沒有夾帶 `Claude` / `Claude Helper` / `Claude的...`，再點「結束」。若一次選取失敗，改成一次處理少量、每次操作後截圖確認再繼續，避免快速連續點擊同一座標被系統誤判為雙擊。
6. 清完後回報：記憶體壓力顏色變化、交換空間數值變化、目前殘留的 claude 程序數量（正常應該只剩 0-1 個，對應使用者正在用的工作階段）。

### 第二部分：硬碟空間檢查

1. 用 `request_access` 請求「系統設定」與「Finder」權限。
2. 開啟系統設定 →「一般」→「儲存空間」，記下總容量、已用、可用空間，並展開各分類（應用程式、文件、照片、開發者等）細項，判斷哪些是正常應用程式佔用（不是垃圾）。
3. 用 Finder 的「前往」→「前往檔案夾」（用選單操作，不要用 Cmd+Shift+G 快速鍵，實測某些情況不會觸發），依序檢查：
   - `~/Library/Caches`
   - `~/Library/Application Support`（看有沒有異常肥大的資料夾，例如瀏覽器、雲端同步軟體）
   - `~/Library/Group Containers`（OneDrive、Dropbox 等雲端同步軟體常在這裡堆積本機快取，是最常見的大宗垃圾來源）
   - `~/Library/Containers`
   - `~/Downloads`
   每個資料夾點兩下「大小」欄位標題排序由大到小，找出前幾名。看到已刪除 App 的資料夾時，記下來交給 Path C。
4. 特別注意：`~/Library/Application Support/Claude/vm_bundles`（通常十幾 GB）是 Cowork / Claude Code 沙盒環境的核心映像檔，不是垃圾，絕對不要建議刪除。
5. 若發現 OneDrive 本機快取異常肥大：
   - 不要嘗試用 `request_access` 開啟 OneDrive App，目前系統辨識不到這個 App 名稱會失敗。
   - 改為指導使用者自己操作：點選單列 OneDrive 雲朵圖示 →「...」→「設定」→左側「同步與備份」→「進階」→「檔案隨選 (建議)」區塊裡的「釋出空間」按鈕。這個動作安全、可逆（檔案還在雲端，只是本機不留實體副本），使用者自己點擊即可，效果需要幾分鐘到幾十分鐘背景處理，提醒使用者耐心等待、之後回頭確認可用空間變化。
   - 不要建議使用者手動進去 Group Containers 刪東西，會弄壞 OneDrive 同步資料庫。

### 第三部分：串接 mo（mole）取得更完整診斷（進階，需要 Desktop Commander）

使用者的 Terminal 裡裝了 mole（`mo` 指令，github.com/tw93/mole），比活動監視器、Finder 更完整：`mo status` 給即時健康分數與硬體數據，`mo analyze` 給視覺化磁碟分析，`mo clean/uninstall/purge/installer` 有 `--dry-run` 預覽模式。只有使用者自己提到 mo/mole，或明確要求把這套檢查流程跟 mo 串起來時才進入這部分。

**限制**：這部分一樣依賴 Desktop Commander（Terminal 在 computer-use 裡不能打字），如果 Step 0 已經判定沒連線，直接告訴使用者：要讀 mo 的資料需要先連上 Desktop Commander，或者使用者自己跑 `mo status --json` 之類的指令、把結果貼給我看，我一樣能幫忙解讀。

Desktop Commander 連上後，只執行唯讀／預覽指令：`mo status --json`、`mo analyze --json [路徑]`、`mo clean --dry-run --debug`、`mo uninstall --dry-run`、`mo purge --dry-run`、`mo installer --dry-run`。把輸出整合進回報。

**絕對不要**執行 `mo clean`、`mo uninstall`、`mo purge`、`mo installer`、`mo optimize`、`mo remove` 這些真正會刪除/改動系統的指令——即使使用者已經看過 dry-run 結果、明確說「執行吧」也一樣。看完 dry-run 後，把「使用者可以自己執行的指令」列出來給他複製貼上，不要代勞。

使用者沒裝 mo 的話不用主動推薦安裝，這是選配加值，不是預設流程。

---

## Path C：已刪除 App 的殘留檔案與權限清理

使用者刪掉 App 後，常留下設定檔、快取、登入憑證、背景服務（LaunchAgents）與隱私權限項目。健康檢查時主動列出這類殘留；使用者要求清殘留時走這條路。

### C0. 先讀 App 清冊，自動找出已移除的 App（2026-11-16 起）

使用者的「App更新檢查」程式（`~/Documents/Claude/App更新檢查`，有排程自動執行）每次執行都會透過 `app_inventory.py` 產出：
- `inventory.json`：目前已安裝的**所有** App（`/Applications`、`/System/Applications`、`~/Applications`），每筆有 `name`、`bundle_id`、`version`、`path`、`app_store`，另有 `generated_at`。
- `inventory_changes.jsonl`：累積的變動紀錄，一行一筆，`change` 為 `baseline`／`removed`／`added`，只增不刪。

每次走 Path C（或完整健檢）時：
1. 申請該資料夾的存取權（唯讀），讀這兩個檔。檔案不存在代表排程還沒跑過新版，請使用者先執行一次「檢查App更新.app」。
2. 檢查 `inventory.json` 的 `generated_at`：超過 7 天代表排程可能沒在跑，提醒使用者。
3. **已移除的 App**：取 `inventory_changes.jsonl` 裡 `change` = `removed` 的項目（之後又出現同一 `bundle_id` 的 `added` 代表重新安裝了，跳過）。用它的 `bundle_id` 與廠商前綴去 C2 掃描殘留。同一筆紀錄下次還會出現，掃不到殘留就回報「已清乾淨」。
4. **全面盤點（補充）**：把 `~/Library` 各子資料夾（Application Support、Containers、Group Containers、Preferences、Caches、HTTPStorages、LaunchAgents 等）裡的資料夾名稱，對照 `inventory.json` 所有 `bundle_id` 與其廠商前綴，找不到主人的列為「疑似殘留」。這用來抓清冊建立之前就刪掉的 App（例如 Arc、Brave、Opera、Chromium、CEF）。`com.apple.*` 與系統項目、C1 的共用資料、Path C 禁區略過。「疑似殘留」一律列清單請使用者確認，不自動刪。
5. 不要修改這兩個檔案，它們由程式管理。

### C1. 判斷擁有者是否還在用（2026-11-16 定案：方案 A）

**主判斷＝實際有沒有安裝；輔助＝「App更新檢查」清單當保護名單。** 兩者都「否」才列為殘留候選，任一為「是」就保留。

1. **實際安裝檢查（主）**：優先用 C0 的 `inventory.json`（有識別碼，最準）。清冊太舊或不存在時，改用以下方式確認（device_bash 讀不到 `/Applications`）：
   - `computer_resolve_access` 傳入 App 名稱（可一次傳多個寫法，例如「Copilot」「Microsoft 365 Copilot」）：回到 `notInstalled` 代表沒安裝（不會跳任何提示給使用者，最快）。
   - 名稱不確定時，用 Finder 開「應用程式」，點清單後直接打字（type-select）找；type-select 會跳到「最接近」的項目，必須核對選中的名稱是否完全相符。
   - 另外檢查 `~/Applications`（使用者自製的 `改寫.app`、`翻譯.app` 在這裡）。
2. **保護名單（輔）**：讀 `~/Documents/Claude/App更新檢查/results.json` 的 `rows[].name`（需先申請該資料夾的存取權，唯讀）。名單上的 App 一律保留。
   - 這份清單只涵蓋「查得到更新來源」的 App，所以**「不在清單上」不等於沒用**：macOS 內建 App、沒有更新來源的 App（例如 Notion Calendar）、終端機工具（Claude Code、Homebrew、mole）都不在清單上，但不能當殘留。
3. **殘留名稱對應擁有者**：用 bundle id 的廠商前綴判斷，例如 `com.openai.*`／`ChatGPTHelper`／`Codex` → ChatGPT、Codex；`ai.perplexity.*`／`CometUpdater` → Perplexity、Comet；`com.google.GeminiMacOS*`／`group.com.google.gemini` → Gemini；`com.microsoft.m365copilot`／`*.com.microsoft.copilot.*` → Copilot。同一廠商可能有多個產品（Perplexity App 與 Comet 瀏覽器），每個產品都要確認沒安裝。
4. **同廠商的共用資料一律保留**：名稱含 `common`、`shared`、`Office` 等、由同廠商多個產品共用的資料夾（例如 `group.com.google.common` 是 Chrome、Google Drive 共用；Microsoft Office 的共用容器），只要該廠商還有任何產品在用就不動。只刪名稱明確指向「已刪除產品」的項目。
5. 同一個資料夾可能被多個產品共用（例如 `~/.codex` 同時是 ChatGPT 桌面版的 Codex 功能與 Codex CLI 的設定目錄），要確認使用者兩者都不用。
6. **終端機工具的設定資料夾**（家目錄下的 `~/.gemini`、`~/.codex` 等）常不屬於桌面 App，而是 CLI 或其他程式（例如 Grok Bot 派工給 Gemini）在用。檢查修改時間，若最近仍在寫入要先告訴使用者、預設保留；使用者同意刪除時一律**移到垃圾桶、不永久刪除**，並提醒使用者觀察一兩天，確定沒有程式出錯再清空垃圾桶；若出錯就從垃圾桶放回原處。

### C2. 掃描（device_bash，唯讀）
1. 用 `device_request_folder_access` 申請 `~/.<app>`（家目錄下的隱藏設定資料夾）、`~/Library`、`~/Applications`。申請前用一句話說明：**這只是授權我讀寫這些「已存在」的資料夾，不會建立任何新資料夾或檔案，授權只在本次對話有效**（2026-11-16 使用者曾誤以為會多建資料夾而拒絕）。
2. 用廠商前綴與 App 名稱搜尋，範圍：`Preferences`、`HTTPStorages`、`WebKit`、`Caches`、`Logs`、`Sounds`、`Application Scripts`、`Saved Application State`、`Containers`、`Group Containers`，用 `du -sh` 附大小。
3. device_bash 看不到內容或刪不掉的位置（Permission denied / Operation not permitted），改用 Finder：`Application Support`、`LaunchAgents`、`Cookies`，以及 `Containers` 與 `Group Containers` 裡帶 `.com.apple.containermanagerd.metadata.plist` 的資料夾。
4. **大小以 Finder 為準**：`Containers`、`Group Containers` 內部受 macOS 保護，device_bash 的 `du` 會嚴重低估（2026-11-16 實例：Microsoft 365 Copilot 容器 du 顯示 48K，Finder 實際 1.99 GB）。列清單時這兩類標注「大小待 Finder 確認」，實際大小用 Finder 的「大小」欄位或完成後回報。
5. **Finder 顯示名稱 ≠ 資料夾名稱**：`Containers` 裡許多資料夾在 Finder 顯示的是 App 顯示名稱（例如 `com.microsoft.m365copilot` 顯示為「Microsoft 365 Copilot」、`com.google.GeminiMacOS.WidgetExtension` 顯示為「Gemini」）。用 bundle id 找不到時，改用 App 名稱找，並核對路徑列。

### C3. 列清單 → 使用者確認
用 AskUserQuestion 一次列出：可直接刪的項目與總大小、保護區項目、隱私權限項目，註明「永久刪除不能復原」；含登入憑證（如 `auth.json`）要點名；終端機工具的設定資料夾單獨列為一個選項。使用者對某個 App 說「可以照同樣方式清掉」時，視為對該 App 殘留的同意，但仍要先做 C1 的安裝檢查。

### C4. 刪除
- **一般位置**：`device_request_delete_permission`（只列需要的資料夾根目錄）→ device_bash `rm -rf` 逐項刪除 → 再搜一次確認歸零。
- **保護區**：需要 `computer_request_full_control`（背景模式下 Finder「前往檔案夾」對話框按不了 Return，實測走不通）。流程：
  1. 點選單列「Go」→「Go to Folder…」開啟對話框。不要依賴 `cmd+shift+G`：系統設定的「隱私權與安全性」面板開著時，它常搶走鍵盤焦點，快速鍵送不到 Finder。
  2. `cmd+A` 清空 → 輸入路徑 → Return。要回家目錄也用這個對話框輸入 `~/`。**不要用 `cmd+shift+H` 或其他 Finder 導覽快速鍵**（2026-11-16 `cmd+shift+H` 反而跳到「應用程式」並選中 Adobe Acrobat，若接著按刪除會刪錯 App）。每次導覽後先截圖確認視窗標題是目標資料夾，再進行下一步。
  3. 點清單空白處取得焦點 → 打資料夾名稱（type-select）→ **用 zoom 核對選中的名稱與路徑列**，確定完全相符才按 `cmd+backspace` 移到垃圾桶。
  4. **不要用 `shift+down` 多選鄰近項目**：相鄰的不一定是同一家（2026-11-16 選 Gemini 容器時，下一列是 `com.microsoft.OneDrive-mac.FinderSync`，差點一起刪掉）。一次只選一項、核對、刪除；只有在 zoom 確認每一列都是目標後，才可以一次刪多項。
  5. Containers 找不到時先按「Name」欄位排序再找（見 C2 第 5 點）；Group Containers 裡以 `.app` 結尾的項目會顯示成種類「Application」、不顯示副檔名。
  6. 家目錄的隱藏資料夾用 `cmd+shift+.` 顯示，處理完再按一次隱藏。
- **Finder 操作禁忌**：不要憑座標盲點 Finder 視窗的標題列或工具列附近（2026-11-16 曾誤點「新增檔案夾」，在「應用程式」裡多建一個 untitled folder）。點之前先截圖確認位置；選取到非目標項目時絕不能按刪除。
- 外接螢幕：截圖看不到視窗時，用 `computer_switch_display` 切換螢幕；系統設定可能會跳到最前面，先點 Dock 的 Finder 圖示再操作。
- 完成後 `computer_release_full_control`，用 device_bash 再搜一次確認歸零，並提醒使用者自己清空垃圾桶。

### C5. 隱私權限（系統設定 → 隱私權與安全性）
- computer-use 無法取得「Privacy & Security」面板擴充的權限（`com.apple.settings.PrivacySecurity.extension` 解析不到），點擊清單內部會被擋；移除項目又需要管理員密碼或 Touch ID。**這部分一律交給使用者**，並給他逐步說明：系統設定左上搜尋框輸入「Full Disk Access」→ 點項目名稱讓整列反白（不要點開關）→ 按清單最下方左邊的「−」（看不到就捲到清單底部）→ Touch ID／密碼確認。
- 確認某個灰色項目還在不在：在項目上按右鍵 →「Show in Finder」，Finder 沒反應或打不開就代表原檔已不在。
- 刪掉 App 後，macOS 有時會自動移除它的權限項目（2026-11-16 刪除 Codex Computer Use 後就自動消失），先截圖確認再請使用者動手。
- 要檢查的分類：完全取用磁碟、輔助使用、螢幕與系統錄音、自動化、輸入監控。
- 開關為「關」的項目沒有任何權限，移除只是讓清單乾淨；開關為「開」的未知項目才有安全意義（例如 `bash` 開著完全取用磁碟，代表任何 bash 腳本都能讀寫整顆硬碟，要提醒使用者確認用途）。

### 權限清單「同名雙生」判讀
- `applet`：用工作指令碼編輯程式／Automator 做的小程式，執行檔一律叫 applet，所以不同小程式會同名（例如使用者的「檢查App更新.app」）。
- 小寫 `claude` 是 Claude Code 指令列程式，大寫 `Claude` 是桌面 App，兩者不同、不能當重複刪。
- 黑色 exec 圖示＝指令列執行檔；灰色格狀圖示＝沒有圖示或原檔已找不到。

### Path C 禁區
- `~/Library/Application Support/Claude`（含 vm_bundles）、`Claude-3p`、`~/.claude`、`~/.local`（Claude Code）、`~/.grokbot` 與 `grok-bot-computer-use`、使用者自製的 `com.<user>.*`（`~/Applications/改寫.app`、`翻譯.app`、`com.<user>.appupdatecheck.plist`、`~/Documents/Claude/App更新檢查`）一律不動。
- 仍在使用的廠商的共用資料（見 C1 第 4 點）不動。
- 不確定屬於哪個 App 的項目只列出、不刪。

---

## 安全界線（Path A、Path B、Path C、mo 全部適用）

- **絕對不要**自己清空垃圾桶，或在使用者確認清單前刪除任何檔案。唯一例外是 Path C：使用者確認清單後，已刪除 App 的殘留可以由我刪除（一般位置永久刪除、保護區與終端機工具設定資料夾移到垃圾桶）。使用者自己的文件、Downloads、快取資料夾仍只列清單、由使用者動手。
- **絕對不要**使用 sudo 或任何需要提權的指令。
- 輸入密碼、Touch ID 驗證一律由使用者自己做。
- 結束背景程序（如異常殘留的小寫 `claude` CLI 程序）不算刪除資料，可以直接執行，但僅限確認過是單純殘留程序、不是使用者正在用的工作階段或 App 核心程序時才動手。
- 若無法判斷某個項目是垃圾還是正在使用中的資料，回報給使用者讓他自己決定，不要自作主張。
- Path A 的收集階段全程唯讀。清理一律依上方「清理流程」三分類處理。本節與「清理流程」若有出入，以本節第一條為準。

## 回報格式（總則）

用繁體中文，簡潔直接，不要套用制式條列報告格式，除非資訊量大到非用列點不可。清楚講：發現了什麼、佔多少空間/資源、判斷是不是垃圾、建議怎麼處理、由誰執行（我或使用者）。若資料一部分來自 mo，標一下是 mo 給的數字還是活動監視器/Finder/Desktop Commander 看到的，避免使用者搞混來源。