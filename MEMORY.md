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
