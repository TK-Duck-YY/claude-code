# MEMORY — 決策紀錄

## 2026-11-13 建立 skill 倉庫

**決定**：採用 B 方案——以 GitHub 私人 repo `TK-Duck-YY/claude-code` 作為自建 Cowork skill 的版本控管倉庫。

**原因**：自建 skill 數量增加，缺乏版本紀錄；放上 GitHub 可追蹤每次修改、可退回舊版、可跨電腦同步。

**放棄的選項**：
- A 方案（只在 GitHub 找開源工具推薦）：不會累積成自己的資產。
- C 方案（找開源專案 → fork → 改造成 skill）：目前沒有要找的具體程式；日後需要時再用「GitHub 找：〈需求〉」啟動。
- 另建新 repo（如 `cowork-skills`）：需另行手動建立；現有空 repo 可直接使用，名稱日後可改。

**收錄範圍**：
- 收錄：13 個自建 skill（skills/）、1 個開源 skill prompt-master（forks/）。
- 不收：19 個 Anthropic 內建 skill（docx、xlsx、pptx、pdf、skill-creator、canvas-design 等），因官方會自動更新，自存副本會過期。

**隱私處理**：個人姓名與公司資料夾路徑已遮蔽；repo 維持私人。

## 2026-11-16 同步 mac-health-check 新版與 app-update-check 工具

**決定**：以 base64 同步包（SHA-256 驗證通過）更新 `skills/mac-health-check/SKILL.md`，並新增 `tools/app-update-check/`（check_updates.py、app_inventory.py、MEMORY.md）。

**原因**：mac-health-check 新增 Path C（已刪除 App 的殘留檔案與權限清理），需要 app_inventory.py 產出的 App 清冊與累積移除紀錄才能自動找出已移除的 App；工具與 skill 一起納入版本控管。

**放棄的選項**：
- 只更新 SKILL.md、不收工具程式：Path C 依賴的清冊程式會沒有版本紀錄。
- 工具放在 skills/ 底下：它是獨立排程程式、不是 skill，故另開 tools/ 目錄。

## 2026-11-16 移除 Desktop Commander，mac-health-check 改寫

**決定**：移除 Claude 的 Desktop Commander 外掛；`skills/mac-health-check/SKILL.md` 刪除 Path A（Desktop Commander 深度掃描）與「先判斷有沒有連上」的步驟，改成固定流程（CPU／記憶體 → 硬碟 → 電池與維護 → 評分），只用 computer-use 背景工具與 device_bash；需要 macOS 指令的數據改為列出指令請使用者在 Terminal 執行後貼回。

**原因**：
- Desktop Commander 靠 `npx`（Node.js）啟動，本機沒裝 Node.js，至少從 2026-11-05 起每次都啟動失敗。
- 健檢與清殘留在沒有它的情況下已能完成；真的需要在 Mac 上跑終端機指令時，已有 Claude Code。
- 外掛標示「無需詢問即可執行程式碼」，留著不用不符合「越精實越好」的目標；它附帶的 skill 也會跟 mac-health-check 搶觸發詞。

**放棄的選項**：
- 安裝官方 Node.js（nodejs.org）保留外掛：多一套執行環境，換到的只有在對話裡直接跑 Mac 指令。
- 用 Homebrew 安裝 Node.js：要先多裝一套 Homebrew。
- 只關閉外掛開關、不移除：效果相同，但使用者選擇直接移除。

**同時修正**：
- Path C 的安裝檢查改以系統查詢為主（`computer_list_apps` 用廠商關鍵字查、`computer_resolve_access` 看 `didYouMean`），App 清冊降為線索：清冊只掃應用程式資料夾往下一層，會漏掉裝得更深的 App 與裝在 `~/Library` 的元件。
- 保護區刪除改用實測可行的背景方法（Go → Library、展開三角形、核對路徑列、File → Move to Trash），全螢幕控制降為備案。
