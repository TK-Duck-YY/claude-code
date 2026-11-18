#!/bin/bash

#
# 檔案自動化處理框架 - Bash 模板
# 應用場景：CSV 資料驗證與清理
#

# ============ 配置 ============
SOURCE_FILE="/path/to/data.csv"           # 原始參考文件
OUTPUT_DIR="/path/to/output"              # 輸出資料夾（可與源相同）
LOG_FILE="automation_log_$(date +%Y%m%d).txt"

# ============ 模組 1: 初始化與驗證 ============
initialize() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 開始處理檔案: $SOURCE_FILE" >> "$LOG_FILE"
    
    # 驗證原始文件存在
    if [ ! -f "$SOURCE_FILE" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 原始文件缺失: $SOURCE_FILE" >> "$LOG_FILE"
        echo "系統通知：找不到原始文件，流程中止"
        return 1
    fi
    
    # 記錄原始文件狀態
    ORIGINAL_SIZE=$(stat -f%z "$SOURCE_FILE" 2>/dev/null || stat -c%s "$SOURCE_FILE" 2>/dev/null)
    ORIGINAL_MTIME=$(stat -f%m "$SOURCE_FILE" 2>/dev/null || stat -c%Y "$SOURCE_FILE" 2>/dev/null)
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 驗證原始文件: 成功 (大小: $ORIGINAL_SIZE bytes)" >> "$LOG_FILE"
    return 0
}

# ============ 模組 2: 檔案複製 ============
copy_file() {
    TEMP_FILE="/tmp/temp_$(date +%Y%m%d%H%M%S).csv"
    
    if ! cp "$SOURCE_FILE" "$TEMP_FILE" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 複製失敗" >> "$LOG_FILE"
        echo "系統通知：無法複製檔案"
        return 1
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 複製副本到臨時位置: $TEMP_FILE" >> "$LOG_FILE"
    return 0
}

# ============ 模組 3: 專案處理 ============
process_file() {
    local temp_file=$1
    
    # 檢查 CSV 結構
    if ! head -n 1 "$temp_file" | grep -q "name,salary,department"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] CSV 結構不符（需包含 name,salary,department 欄位）" >> "$LOG_FILE"
        return 1
    fi
    
    # 去重：使用 awk 移除重複行
    if ! awk '!seen[$0]++' "$temp_file" > "$temp_file.tmp"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 去重失敗" >> "$LOG_FILE"
        return 1
    fi
    mv "$temp_file.tmp" "$temp_file"
    
    # 排序（按姓名）。整檔一起排會把標題列排進資料裡，所以先留住第一行。
    if ! { head -n 1 "$temp_file"; tail -n +2 "$temp_file" | sort -t',' -k1,1; } > "$temp_file.tmp"; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 排序失敗" >> "$LOG_FILE"
        return 1
    fi
    mv "$temp_file.tmp" "$temp_file"
    
    # 驗證每行欄位數（應為 3 個）
    local invalid_lines=$(awk -F',' 'NF != 3 && NR > 1 {print}' "$temp_file" | wc -l)
    if [ "$invalid_lines" -gt 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] 發現 $invalid_lines 行欄位數不符" >> "$LOG_FILE"
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 執行資料清理與驗證: 成功" >> "$LOG_FILE"
    return 0
}

# ============ 模組 4: 重命名與輸出 ============
output_file() {
    local temp_file=$1
    
    # 生成輸出檔名
    local today=$(date +%y%m%d)
    local basename=$(basename "$SOURCE_FILE" | sed "s/\.[^.]*$//")
    local ext=$(echo "$SOURCE_FILE" | sed -n 's/.*\(\.[^.]*\)$/\1/p')
    local output_filename="${basename}_${today}${ext}"
    local output_path="$OUTPUT_DIR/$output_filename"
    
    # 檢查是否已存在
    if [ -f "$output_path" ]; then
        local old_mtime=$(stat -f%m "$output_path" 2>/dev/null || stat -c%Y "$output_path" 2>/dev/null)
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [WARNING] 輸出檔案已存在，將被覆蓋: $output_path (舊版本修改時間: $old_mtime)" >> "$LOG_FILE"
    fi
    
    # 移動臨時檔案為最終輸出
    if ! mv "$temp_file" "$output_path" 2>/dev/null; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 輸出檔案保存失敗" >> "$LOG_FILE"
        return 1
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 輸出檔案: $output_filename" >> "$LOG_FILE"
    
    # 驗證輸出檔案
    local output_size=$(stat -f%z "$output_path" 2>/dev/null || stat -c%s "$output_path" 2>/dev/null)
    if [ -n "$output_size" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 輸出檔案驗證: 成功 (大小: $output_size bytes)" >> "$LOG_FILE"
        echo "$output_path"
        return 0
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 輸出檔案驗證失敗" >> "$LOG_FILE"
        return 1
    fi
}

# ============ 模組 5: 驗證與日誌 ============
verify_and_finalize() {
    # 驗證原始文件未被修改
    local current_size=$(stat -f%z "$SOURCE_FILE" 2>/dev/null || stat -c%s "$SOURCE_FILE" 2>/dev/null)
    local current_mtime=$(stat -f%m "$SOURCE_FILE" 2>/dev/null || stat -c%Y "$SOURCE_FILE" 2>/dev/null)
    
    if [ "$ORIGINAL_SIZE" != "$current_size" ] || [ "$ORIGINAL_MTIME" != "$current_mtime" ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 原始文件已被修改！" >> "$LOG_FILE"
        echo "系統通知：原始文件意外修改！"
        return 1
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 原始文件驗證: 完整未改變" >> "$LOG_FILE"
    fi
    
    return 0
}

# ============ 主流程 ============
main() {
    # 模組 1: 初始化
    if ! initialize; then
        return
    fi
    
    # 模組 2: 複製
    if ! copy_file; then
        return
    fi
    
    # 模組 3: 處理
    if ! process_file "$TEMP_FILE"; then
        rm -f "$TEMP_FILE"
        return
    fi
    
    # 模組 4: 輸出
    local output_path
    output_path=$(output_file "$TEMP_FILE")
    if [ -z "$output_path" ]; then
        return
    fi
    
    # 模組 5: 驗證
    if verify_and_finalize; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [INFO] 處理完成: 成功" >> "$LOG_FILE"
        echo "✓ 成功！輸出檔案位置：$output_path"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] [ERROR] 處理完成: 失敗" >> "$LOG_FILE"
    fi
}

# 執行主流程
main
