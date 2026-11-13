# 文件自動化處理框架

## 📋 概述

此技能定義在**保護原始數據**的前提下，實現文件自動化處理的通用原則與實踐模板。適用於 Excel、Word、PDF 等檔案的批量處理、計算、提取任務。

## 📁 檔案結構

```
file-automation-framework/
├── SKILL.md                      # 技能文檔（主要內容）
├── test_cases.json              # 12 個測試用例
├── template_payroll.py          # Python 模板（薪資計算）
├── template_csv_cleanup.sh      # Bash 模板（CSV 清理）
└── README.md                     # 本檔案
```

## 🎯 核心原則

### 1️⃣ 絕對保護原始檔案
- 所有操作作用於副本
- 執行前驗證原始文件存在
- 執行後驗證原始文件未被修改

### 2️⃣ 標準化工作流程
```
驗證 → 複製 → 處理 → 重命名 → 日誌
```

### 3️⃣ 檔名規範
```
原始名_YYMMDD.副檔名

範例：
- salary_sheet.xlsx → salary_sheet_240315.xlsx
- data.csv → data_240316.csv
```

### 4️⃣ 同日覆蓋機制
- 同一天內重複處理，後者覆蓋前者
- 無序號，檔名統一
- 日誌記錄覆蓋事實

## 📚 主要內容

| 章節 | 說明 |
|------|------|
| **核心原則** | 文件保護、工作流程、命名規範 |
| **實現指南** | 原始文件驗證、語言選擇、錯誤處理 |
| **腳本模板** | Python / Bash 完整實現（5 個模組） |
| **進階用法** | 資料夾監視、自動化觸發 |
| **檢查清單** | 執行前後的驗證項目 |

## 🚀 快速開始

### 方案 A: 使用 Python（Excel 薪資計算）

```bash
# 1. 複製模板
cp template_payroll.py my_project.py

# 2. 編輯配置
# 修改 SOURCE_FILE 和 OUTPUT_DIR

# 3. 修改業務邏輯（模組 3）
# 根據需求調整計算公式

# 4. 測試
python my_project.py

# 5. 檢查輸出
ls -la output/salary_sheet_240315.xlsx
cat automation_log_20240315.txt
```

### 方案 B: 使用 Bash（CSV 資料清理）

```bash
# 1. 複製模板
cp template_csv_cleanup.sh my_project.sh
chmod +x my_project.sh

# 2. 編輯配置
# 修改 SOURCE_FILE 和 OUTPUT_DIR

# 3. 修改處理邏輯（模組 3）
# 根據需求調整去重、驗證、排序邏輯

# 4. 測試
./my_project.sh

# 5. 檢查輸出
ls -la output/data_240315.csv
cat automation_log_20240315.txt
```

## 📋 測試用例

技能附帶 12 個測試用例，涵蓋：
- ✅ 語言推薦邏輯（3 個）
- ✅ 檔名規範與覆蓋（3 個）
- ✅ 原始文件保護驗證（2 個）
- ✅ 錯誤處理（2 個）
- ✅ 完整工作流程（1 個）
- ✅ 日誌記錄（1 個）

執行測試：
```bash
python -m pytest test_cases.json  # 若使用測試框架
```

或手動驗證各測試場景（見 test_cases.json）。

## 🔧 常見修改

### 修改業務邏輯（Python）
```python
# 在 process_file() 中修改
# 範例：計算年終獎金
if performance > 80:
    bonus = salary * 0.2  # 改為 20%
    ws[f"E{row}"] = bonus
```

### 修改業務邏輯（Bash）
```bash
# 在 process_file() 中修改
# 範例：額外的資料驗證
if ! grep -q "^[A-Za-z].*,[0-9].*," "$temp_file"; then
    echo "資料驗證失敗" >> "$LOG_FILE"
    return 1
fi
```

### 啟用資料夾監視（Linux/Mac）
```bash
# 使用 inotifywait 監視新檔案
while inotifywait -e close_write /path/to/source/; do
    ./my_project.sh
done
```

## ⚠️ 常見陷阱

| 問題 | 原因 | 解決 |
|------|------|------|
| 原始檔案被修改 | 直接操作原始檔案 | 務必複製副本，操作副本 |
| 檔名重複衝突 | 忘記加日期戳 | 按規範 `name_YYMMDD.ext` |
| 檔案被鎖定 | 他人開啟檔案中 | 加重試機制（模板已內含） |
| 日誌難以追蹤 | 日誌格式不統一 | 使用統一的 `[YYYY-MM-DD HH:MM:SS] [LEVEL]` 格式 |

## 📞 常見問題

**Q: 能否監視資料夾自動觸發？**  
A: 可以。見「進階：監視與自動化」章節。

**Q: 同一天多次處理，如何保留舊版本？**  
A: 自動覆蓋。若需保留，手動另存或搭配 Git 版本控制。

**Q: 支援什麼檔案格式？**  
A: 任何格式（Excel、CSV、PDF、Word 等）。模板示例僅供參考，邏輯可自行擴展。

**Q: 多個檔案如何並行處理？**  
A: 修改主流程為迴圈，或分別觸發。注意日誌併發寫入。

## 📖 更多資訊

詳見 `SKILL.md` 的各章節：
- 完整的 5 個模組框架
- 詳細的錯誤處理表
- 日誌標準與格式
- 進階監視與自動化範例

## 版本

- **v1.0** - 初始版本，覆蓋模式（同日覆蓋）
- 測試日期：2024-03-15
- 支援語言：Python 3.8+, Bash 4.0+

---

**最後更新**：2024-03-15
