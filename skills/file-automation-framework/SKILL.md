---
name: file-automation-framework
description: 【強制前置步驟】在執行任何 bash、Python 或腳本操作之前，只要任務涉及以下任一情況，必須立即讀取此技能，不得跳過：(1) 對 .xlsx/.xls/.csv 檔案進行任何寫入、更新、修改（包括排程資料寫入、儲存格數值更新、openpyxl/xlwt/pandas 操作）；(2) 批量編輯、生成或填寫 .docx Word 文件；(3) 合併、拆分、提取或修改 PDF 內容；(4) 用 bash/Python/VBA 腳本自動化處理上述任何檔案格式。此技能提供：原始文件保護機制、5 模組標準腳本結構、語言選擇決策矩陣、日期命名規範（原始名_YYMMDD）、完整錯誤處理與日誌模板。未事先讀取此技能而直接操作檔案，將導致原始資料無備份被覆蓋的高風險。
---

# 文件自動化處理框架

此技能定義在**保護原始數據**的前提下，實現文件自動化處理的通用原則與實踐模板。

## 核心原則

### 1. 絕對保護原始參考文件
- **原則**：原始文件必須保持完全不動
- **實現方式**：所有處理作業操作於檔案副本
- **檢查點**：執行前必須驗證原始文件存在；執行後必須確認原始文件完整未改變

### 2. 工作流程框架

```
[輸入資料夾]
    ↓
[驗證原始文件存在] ← 如無文件，系統通知警示並中止
    ↓
[複製原始檔案到臨時位置]
    ↓
[對副本進行專案處理]
    ├─ 內容編輯 (Word/PDF)
    ├─ 數據計算 (Excel 公式)
    ├─ 資料提取與合併
    └─ 其他業務邏輯
    ↓
[重命名輸出檔案] → 格式: 原始名_YYMMDD[_序號].副檔名
    ↓
[輸出到結果位置]（同一資料夾內）
    ↓
[保存處理日誌]
```

### 3. 檔名規範

**輸出檔案命名格式：**
```
{original_name}_{YYMMDD}.{extension}
```

**範例：**
- 原始檔案：`salary_sheet.xlsx`
- 輸出（2024年3月15日）：`salary_sheet_240315.xlsx`
- 同日再次輸出：`salary_sheet_240315.xlsx`（覆蓋前一版本）
- 次日輸出（2024年3月16日）：`salary_sheet_240316.xlsx`

**規則：**
- 日期使用系統當日日期（YYMMDD 格式）
- 同一日期輸出多次時，後者覆蓋前者（無序號）
- 不涉及格式轉換：輸入什麼格式，輸出什麼格式
- 若需要保留歷史版本，手動另存或搭配版本控制系統

---

## 實現指南

### A. 原始文件驗證

**執行時檢查清單：**

```
☐ 原始文件路徑正確無誤
☐ 原始文件存在且可讀取
☐ 檔案無損壞、無編碼錯誤
☐ 檔案權限允許讀取
☐ 若檔案被鎖定（他人開啟中），系統通知並重試
```

**檢查失敗的處理：**
- 若原始文件缺失 → **系統通知警示**（在專案對答匡中彈出）
- 若檔案損壞 → 紀錄錯誤日誌，通知使用者
- 若權限不足 → 記錄並通知

---

### B. 語言選擇邏輯

根據專案背景與工具，推薦指令碼語言：

| 專案情境 | 推薦語言 | 理由 |
|---------|---------|------|
| **Excel 計算、樞紐分析、宏應用** | VBA 或 Python | VBA 直接在 Excel 內運行；Python 跨平台更靈活 |
| **Word 文檔批量編輯、內容提取** | Python (python-docx) | 跨平台，易於維護 |
| **PDF 合併、提取、標記** | Python (PyPDF2/pdfplumber) | 開源、功能完整 |
| **多檔案批量處理（跨格式）** | Python | 統一處理邏輯，避免工具切換 |
| **Bash/Shell 環境下的檔案管理** | Bash | 原生系統環境 |
| **Windows 自動化任務調度** | PowerShell 或 VBA | 系統原生集成 |
| **Linux/Mac 監視資料夾** | Bash + inotifywait/fswatch | 系統級監視工具 |

---

### D. 模板腳本

此技能提供兩份完整的參考實現，涵蓋所有 5 個模組。可直接複製調整使用：

| 語言 | 應用場景 | 檔案名 | 修改項目 |
|------|---------|--------|--------|
| **Python** | Excel 薪資計算 | `template_payroll.py` | `SOURCE_FILE`, `OUTPUT_DIR`, 業務邏輯（模組 3） |
| **Bash** | CSV 資料清理 | `template_csv_cleanup.sh` | `SOURCE_FILE`, `OUTPUT_DIR`, 清理邏輯（模組 3） |

**快速上手：**
1. 複製對應的模板檔案
2. 修改頂部的 `SOURCE_FILE` 和 `OUTPUT_DIR` 路徑
3. 根據業務需求修改模組 3 的處理邏輯
4. 測試：在測試環境運行，驗證輸出檔名和日誌格式
5. 上線：監視資料夾或定時觸發

---

每份腳本應包含以下模組：

#### 模組 1: 初始化與驗證
```
- 定義來源資料夾路徑
- 定義結果資料夾路徑（若不同）
- 初始化日誌系統
- 驗證原始文件存在
- 記錄原始檔案的狀態快照（大小、修改時間）以便後續驗證

【Python 範例】
import os
import logging
from datetime import datetime

# 初始化日誌
logging.basicConfig(
    filename=f"automation_log_{datetime.now().strftime('%Y%m%d')}.txt",
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 驗證原始文件
source_file = "/path/to/salary_master.xlsx"
if not os.path.exists(source_file):
    logging.error(f"原始文件缺失: {source_file}")
    print("系統通知：找不到原始文件，流程中止")
    exit(1)

# 記錄原始文件狀態
original_stat = os.stat(source_file)
original_size = original_stat.st_size
original_mtime = original_stat.st_mtime
logging.info(f"驗證原始文件: {source_file} (大小: {original_size} bytes)")

【Bash 範例】
#!/bin/bash

SOURCE_FILE="/path/to/salary_master.xlsx"
LOG_FILE="automation_log_$(date +%Y%m%d).txt"

# 驗證原始文件
if [ ! -f "$SOURCE_FILE" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 原始文件缺失: $SOURCE_FILE" >> "$LOG_FILE"
    echo "系統通知：找不到原始文件，流程中止"
    exit 1
fi

# 記錄原始文件狀態
ORIGINAL_SIZE=$(stat -f%z "$SOURCE_FILE" 2>/dev/null || stat -c%s "$SOURCE_FILE" 2>/dev/null)
ORIGINAL_MTIME=$(stat -f%m "$SOURCE_FILE" 2>/dev/null || stat -c%Y "$SOURCE_FILE" 2>/dev/null)
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 驗證原始文件: $SOURCE_FILE (大小: $ORIGINAL_SIZE bytes)" >> "$LOG_FILE"
```

#### 模組 2: 檔案複製
```
- 讀取原始檔案
- 創建臨時副本（或直接在記憶體中操作）
- 確認副本創建成功

【Python 範例 - 複製到臨時位置】
import shutil
import tempfile

temp_dir = tempfile.gettempdir()
temp_file = os.path.join(temp_dir, f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx")

try:
    shutil.copy2(source_file, temp_file)
    logging.info(f"複製副本到臨時位置: {temp_file}")
except Exception as e:
    logging.error(f"複製失敗: {e}")
    print("系統通知：無法複製檔案")
    exit(1)

【Bash 範例 - 複製到臨時位置】
TEMP_FILE="/tmp/temp_$(date +%Y%m%d%H%M%S).xlsx"

if ! cp "$SOURCE_FILE" "$TEMP_FILE" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 複製失敗" >> "$LOG_FILE"
    echo "系統通知：無法複製檔案"
    exit 1
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 複製副本到臨時位置: $TEMP_FILE" >> "$LOG_FILE"
fi
```

#### 模組 3: 專案處理
```
- 執行業務邏輯（計算、編輯、提取）
- 捕捉及記錄任何處理過程中的例外

【Python 範例 - Excel 薪資計算】
import openpyxl
from openpyxl.utils import get_column_letter

try:
    wb = openpyxl.load_workbook(temp_file)
    ws = wb.active
    
    # 業務邏輯範例：計算補助（Performance Score > 80 時增加 10% 獎金）
    for row in range(2, ws.max_row + 1):
        performance = ws[f"D{row}"].value  # D 列為 Performance Score
        salary = ws[f"C{row}"].value       # C 列為基本薪資
        
        if isinstance(salary, (int, float)) and isinstance(performance, (int, float)):
            if performance > 80:
                bonus = salary * 0.1
                ws[f"E{row}"] = bonus  # E 列為獎金
                logging.info(f"第 {row} 列: 計算獎金 {bonus} (Performance: {performance})")
    
    wb.save(temp_file)
    logging.info(f"執行計算邏輯: 成功")
    
except Exception as e:
    logging.error(f"處理過程中出現例外: {type(e).__name__}: {e}")
    exit(1)

【Bash 範例 - CSV 資料驗證與清理】
try:
    # 資料驗證：檢查 CSV 結構
    if ! head -n 1 "$TEMP_FILE" | grep -q "name,salary,department"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] CSV 結構不符" >> "$LOG_FILE"
        exit 1
    fi
    
    # 去重：使用 awk 移除重複行
    awk '!seen[$0]++' "$TEMP_FILE" > "$TEMP_FILE.tmp"
    mv "$TEMP_FILE.tmp" "$TEMP_FILE"
    
    # 排序
    sort "$TEMP_FILE" > "$TEMP_FILE.tmp"
    mv "$TEMP_FILE.tmp" "$TEMP_FILE"
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 執行資料清理與驗證: 成功" >> "$LOG_FILE"
    
except {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 處理過程中出現例外: $?" >> "$LOG_FILE"
    exit 1
}
```

#### 模組 4: 重命名與輸出
```
- 取得系統當日日期（YYMMDD）
- 檢查輸出檔名是否已存在
- 若存在，直接覆蓋（無需檢查或提示）
- 將處理結果保存為目標檔名
- 驗證輸出檔案完整性
- 紀錄覆蓋動作到日誌（若有舊版本被覆蓋）

【Python 範例】
import shutil

# 生成輸出檔名
today = datetime.now().strftime("%y%m%d")
name_without_ext, ext = os.path.splitext(source_file)
output_filename = f"{os.path.basename(name_without_ext)}_{today}{ext}"
output_path = os.path.join(output_dir, output_filename)

# 檢查是否已存在（用於覆蓋前記錄）
if os.path.exists(output_path):
    old_mtime = os.stat(output_path).st_mtime
    logging.warning(f"輸出檔案已存在，將被覆蓋: {output_path} (舊版本修改時間: {old_mtime})")

try:
    shutil.move(temp_file, output_path)
    logging.info(f"輸出檔案: {output_filename}")
    
    # 驗證輸出檔案
    if os.path.exists(output_path):
        output_size = os.path.getsize(output_path)
        logging.info(f"輸出檔案驗證: 成功 (大小: {output_size} bytes)")
    else:
        logging.error(f"輸出檔案驗證失敗")
        exit(1)
except Exception as e:
    logging.error(f"輸出檔案保存失敗: {e}")
    exit(1)

【Bash 範例】
# 生成輸出檔名
TODAY=$(date +%y%m%d)
OUTPUT_FILENAME=$(basename "$SOURCE_FILE" | sed "s/\.[^.]*$//" )_${TODAY}$(echo "$SOURCE_FILE" | sed -n 's/.*\(\.[^.]*\)$/\1/p')
OUTPUT_PATH="$OUTPUT_DIR/$OUTPUT_FILENAME"

# 檢查是否已存在
if [ -f "$OUTPUT_PATH" ]; then
    OLD_MTIME=$(stat -f%m "$OUTPUT_PATH" 2>/dev/null || stat -c%Y "$OUTPUT_PATH" 2>/dev/null)
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] 輸出檔案已存在，將被覆蓋: $OUTPUT_PATH (舊版本修改時間: $OLD_MTIME)" >> "$LOG_FILE"
fi

# 移動臨時檔案為最終輸出
if mv "$TEMP_FILE" "$OUTPUT_PATH" 2>/dev/null; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 輸出檔案: $OUTPUT_FILENAME" >> "$LOG_FILE"
    
    # 驗證輸出檔案
    OUTPUT_SIZE=$(stat -f%z "$OUTPUT_PATH" 2>/dev/null || stat -c%s "$OUTPUT_PATH" 2>/dev/null)
    if [ -n "$OUTPUT_SIZE" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 輸出檔案驗證: 成功 (大小: $OUTPUT_SIZE bytes)" >> "$LOG_FILE"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 輸出檔案驗證失敗" >> "$LOG_FILE"
        exit 1
    fi
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 輸出檔案保存失敗" >> "$LOG_FILE"
    exit 1
fi
```

#### 模組 5: 日誌與通知
```
- 紀錄處理開始時間、檔案名、狀態
- 紀錄任何警告或錯誤
- 驗證原始文件未被修改（比對開始時的狀態快照）
- 輸出處理結論（成功/失敗）
- 若失敗，彈出系統通知警示

【Python 範例】
# 驗證原始文件未被修改
current_stat = os.stat(source_file)
current_size = current_stat.st_size
current_mtime = current_stat.st_mtime

if original_size != current_size or original_mtime != current_mtime:
    logging.error(f"原始文件已被修改！大小：{original_size} → {current_size}，修改時間：{original_mtime} → {current_mtime}")
    print("系統通知：原始文件意外修改！")
    exit(1)
else:
    logging.info(f"原始文件驗證: 完整未改變")

logging.info(f"輸出檔案: {output_filename}")
logging.info(f"處理完成: 成功")

【Bash 範例】
# 驗證原始文件未被修改
CURRENT_SIZE=$(stat -f%z "$SOURCE_FILE" 2>/dev/null || stat -c%s "$SOURCE_FILE" 2>/dev/null)
CURRENT_MTIME=$(stat -f%m "$SOURCE_FILE" 2>/dev/null || stat -c%Y "$SOURCE_FILE" 2>/dev/null)

if [ "$ORIGINAL_SIZE" != "$CURRENT_SIZE" ] || [ "$ORIGINAL_MTIME" != "$CURRENT_MTIME" ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 原始文件已被修改！" >> "$LOG_FILE"
    echo "系統通知：原始文件意外修改！"
    exit 1
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 原始文件驗證: 完整未改變" >> "$LOG_FILE"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 輸出檔案: $OUTPUT_FILENAME" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 處理完成: 成功" >> "$LOG_FILE"
```

---

## 錯誤處理建議

| 錯誤情況 | 建議處理方式 | 日誌記錄 |
|---------|-----------|--------|
| 原始文件缺失 | **中止流程，系統通知警示** | 檔名、預期路徑、檢查時間 |
| 檔案被鎖定（他人開啟中） | 重試 3 次，每次間隔 2 秒 | 重試次數、最終結果 |
| 讀取權限不足 | 中止，紀錄檔案路徑與權限信息 | 檔名、需求權限、實際權限 |
| 處理過程中例外 | 捕捉例外，記錄堆棧跟蹤，中止 | 例外類型、行號、內容摘要 |
| 輸出路徑不可寫 | 中止，嘗試備用路徑或提示使用者 | 路徑、可用磁碟空間、權限 |
| 原始文件在處理中被修改 | 檢測變化，中止或重新開始 | 修改時間戳、判斷邏輯 |
| 輸出檔案已存在（同日重複） | 直接覆蓋，記錄覆蓋動作 | 舊檔案修改時間、新檔案生成時間 |

---

## 日誌標準

### 日誌檔案名稱
```
automation_log_{YYYYMMDD}.txt
```

### 日誌記錄格式
```
[YYYY-MM-DD HH:MM:SS] [INFO/WARNING/ERROR] {操作描述}
範例：
[2024-03-15 14:32:10] [INFO] 開始處理檔案: salary_sheet.xlsx
[2024-03-15 14:32:11] [INFO] 驗證原始文件: 成功
[2024-03-15 14:32:12] [INFO] 複製副本到臨時位置: 成功
[2024-03-15 14:32:45] [INFO] 執行計算邏輯: 成功
[2024-03-15 14:32:46] [INFO] 輸出檔案: salary_sheet_240315.xlsx
[2024-03-15 14:32:47] [INFO] 處理完成: 成功
```

### 日誌位置
- 預設位置：與處理檔案相同的資料夾
- 備用位置：專案根目錄下的 `logs/` 子資料夾

---

## 執行檢查清單

在啟動任何文件自動化專案前，確認以下事項：

```
前置條件
☐ 原始參考文件已備份（額外的保險）
☐ 資料夾路徑已確認無誤
☐ 磁碟空間充足（至少原始檔案大小的 2 倍）
☐ 檔案權限已設置（讀取 + 寫入）

指令碼準備
☐ 選定合適的語言（已按建議判斷）
☐ 依模板完成所有 5 個模組
☐ 本地測試通過（測試檔案 ≠ 生產檔案）
☐ 日誌系統已初始化
☐ 錯誤處理邏輯已完備

執行驗證
☐ 執行前再次驗證原始文件存在
☐ 執行後確認原始檔案未被修改（檔案大小、修改時間戳）
☐ 確認輸出檔案按規範命名
☐ 檢查日誌無重大錯誤
☐ 如有失敗，檢視日誌並排查根本原因
```

---

## 進階：監視與自動化

若要實現「資料夾監視 → 自動處理」：

### Bash（Linux/Mac）
```bash
# 使用 inotifywait 監視資料夾變化
while inotifywait -e close_write /path/to/source/; do
  /path/to/process_script.sh
done
```

### PowerShell（Windows）
```powershell
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = "C:\source_folder"
$watcher.Filter = "*.xlsx"
$watcher.IncludeSubdirectories = $false

Register-ObjectEvent -InputObject $watcher -EventName "Created" -Action {
  & "C:\process_script.ps1"
}
```

### Python（跨平台）
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class FileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            process_file(event.src_path)

observer = Observer()
observer.schedule(FileHandler(), path="/source_folder", recursive=False)
observer.start()
```

---

## 範例應用場景

1. **薪資表自動化**：每月從 master.xlsx 複製 → 按部門計算補助 → 輸出為 payroll_240315.xlsx
2. **合約管理**：掃描 PDF → 提取關鍵條款 → 輸出為 contract_summary_240315.txt
3. **報告生成**：合併多個 Excel 工作簿 → 計算統計值 → 輸出為 monthly_report_240315.xlsx
4. **文檔轉換**：批量 Word 檔案 → 提取特定段落 → 輸出為各自的 _240315 版本
5. **數據清理**：原始 CSV → 去重、驗證、格式化 → 輸出為 cleaned_data_240315.csv

---

## 常見問題

**Q: 如果處理耗時很長，監視程序會卡住嗎？**  
A: 建議用非同步方式或背景程序執行，避免阻塞監視器。Python 可用 threading；Bash 可用 `&` 後台執行。

**Q: 原始文件很大，複製副本會很慢？**  
A: 考慮在記憶體中操作（讀取 → 處理 → 輸出），避免磁碟 I/O。某些語言（如 Python）支援串流處理。

**Q: 能否同時處理多個檔案？**  
A: 可以，但需注意：
- 覆蓋邏輯要原子性（避免競態條件）
- 日誌系統要支援併發寫入
- 監視器的事件可能重複觸發，加去重邏輯

**Q: 同一天處理多次，舊版本怎麼辦？**  
A: 直接覆蓋。若需保留歷史，建議：
1. 手動另存副本（另取名稱）
2. 搭配 Git、SVN 等版本控制系統
3. 在處理前自動備份，命名為 `name_YYMMDD_backup_HHmmss.ext`

