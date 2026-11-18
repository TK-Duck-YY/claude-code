# AGENTS.md — 給所有 AI 協作者的共同規則

本倉庫由多個 AI 工具（Claude、Gemini、Grok Bot 等）共同維護，擁有者為 TK-Duck-YY。動手修改前，請先讀完這份規則。

## 1. 語言
- 所有文件、註解、commit 訊息、PR 說明一律使用**繁體中文**。嚴禁簡體中文。
- 程式碼識別字（變數、函式名稱）可用英文。

## 2. 目錄結構
```
skills/<skill-name>/     自建 skill
forks/<skill-name>/      取自開源專案的 skill（必須保留原作者 LICENSE）
tools/<tool-name>/       獨立程式（排程工具等），不是 skill
AGENTS.md                本檔
README.md                繁中目錄，新增或刪除 skill／工具時同步更新
MEMORY.md                決策紀錄
ERRORS.md                試錯紀錄
```
- 資料夾名稱用小寫英文加連字號（kebab-case），必須與 `SKILL.md` 的 `name` 相同。

## 3. SKILL.md 格式
每個 skill 資料夾必須有 `SKILL.md`，開頭為 YAML frontmatter：
```yaml
---
name: skill-name
description: 一段話說明「做什麼」與「什麼情況下觸發」，包含使用者可能說的關鍵詞。
---
```
- 輔助說明放 `references/`，腳本放 `scripts/`，素材放 `assets/`。
- 修改觸發詞時，檢查是否與其他 skill 的 description 重疊。

## 4. 修改流程
1. **不得直接推送到 `main`。** 每次修改另開分支，命名為 `<工具名>/<簡短描述>`，例如 `gemini/chart-generator-fix`、`claude/add-agents-md`。
2. 推送分支後開 Pull Request，說明改了什麼、為什麼改。
3. 預設由擁有者決定是否合併。
   - 擁有者在對話中針對特定 PR 明確同意合併（例如「合併 PR #3」）後，AI 可代為合併該 PR。同意只適用於被點名的那個 PR，不延伸到其他 PR 或之後的新提交。
   - 合併前 AI 必須確認：PR 可合併（無衝突）、檢查（如有）皆通過、PR 內容自同意後沒有新增提交。任一不符就停止並回報擁有者。
   - 未經擁有者明確同意，AI 不得自行合併任何 PR，也不得推送到 `main`。
4. 一個 PR 只處理一件事。

## 5. 紀錄
- **MEMORY.md**：做出重要決定時新增一則，格式：
  ```
  ## YYYY-MM-DD 標題（修改者：Claude／Gemini／Grok Bot）
  **決定**：
  **原因**：
  **放棄的選項**：
  ```
- **ERRORS.md**：某個做法嘗試超過 2 次才成功時記錄（沒用的做法／有用的做法／下次要記得）。
- MEMORY.md 超過約 300 行時，把較舊的紀錄移到 `MEMORY-archive.md`。

## 6. 隱私與安全（本倉庫為公開）
- 禁止寫入：個人姓名、公司名稱、真實資料夾路徑、帳號、密碼、API 金鑰、權杖、內部系統網址、IP、客戶或員工資料。
- 路徑一律用 `~/` 或 `<公司名稱>` 這類佔位符。
- 不得放入使用 skill 處理過的實際檔案（Word、Excel、PDF、簡報等），只放 skill 本身。
- 引入外部開源程式碼前，確認授權允許使用與修改；沒有授權條款的專案不得收錄。

## 7. 不確定時
不確定是否該改、或規則沒有涵蓋時，在 PR 說明中提出問題，由擁有者決定，不要自行猜測。
