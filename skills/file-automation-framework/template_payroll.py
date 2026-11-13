#!/usr/bin/env python3
"""
檔案自動化處理框架 - Python 模板
應用場景：Excel 薪資表自動計算
"""

import os
import logging
import shutil
import tempfile
from datetime import datetime
import openpyxl

# ============ 配置 ============
SOURCE_FILE = "/path/to/salary_master.xlsx"       # 原始參考文件
OUTPUT_DIR = "/path/to/output"                    # 輸出資料夾（可與源相同）
LOG_FILE = f"automation_log_{datetime.now().strftime('%Y%m%d')}.txt"

# ============ 初始化日誌 ============
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

def log_and_print(level, message):
    """同時輸出到日誌和控制台"""
    getattr(logging, level.lower())(message)
    print(f"[{level}] {message}")

# ============ 模組 1: 初始化與驗證 ============
def initialize():
    """驗證原始文件並記錄狀態"""
    log_and_print("INFO", f"開始處理檔案: {SOURCE_FILE}")
    
    # 驗證原始文件存在
    if not os.path.exists(SOURCE_FILE):
        log_and_print("ERROR", f"原始文件缺失: {SOURCE_FILE}")
        print("系統通知：找不到原始文件，流程中止")
        return None
    
    # 記錄原始文件狀態
    original_stat = os.stat(SOURCE_FILE)
    original_size = original_stat.st_size
    original_mtime = original_stat.st_mtime
    
    log_and_print("INFO", f"驗證原始文件: 成功 (大小: {original_size} bytes)")
    
    return {
        "source_file": SOURCE_FILE,
        "original_size": original_size,
        "original_mtime": original_mtime
    }

# ============ 模組 2: 檔案複製 ============
def copy_file(original_info):
    """複製原始檔案到臨時位置"""
    try:
        temp_dir = tempfile.gettempdir()
        temp_file = os.path.join(
            temp_dir,
            f"temp_{datetime.now().strftime('%Y%m%d%H%M%S')}.xlsx"
        )
        
        shutil.copy2(original_info["source_file"], temp_file)
        log_and_print("INFO", f"複製副本到臨時位置: {temp_file}")
        return temp_file
    except Exception as e:
        log_and_print("ERROR", f"複製失敗: {e}")
        print("系統通知：無法複製檔案")
        return None

# ============ 模組 3: 專案處理 ============
def process_file(temp_file):
    """執行業務邏輯（薪資計算）"""
    try:
        wb = openpyxl.load_workbook(temp_file)
        ws = wb.active
        
        # 業務邏輯：Performance Score > 80 時計算 10% 獎金
        for row in range(2, ws.max_row + 1):
            try:
                performance = ws[f"D{row}"].value
                salary = ws[f"C{row}"].value
                
                if isinstance(salary, (int, float)) and isinstance(performance, (int, float)):
                    if performance > 80:
                        bonus = salary * 0.1
                        ws[f"E{row}"] = bonus
                        logging.debug(f"第 {row} 列: 計算獎金 {bonus} (Performance: {performance})")
            except Exception as cell_error:
                logging.warning(f"第 {row} 列處理異常: {cell_error}")
                continue
        
        wb.save(temp_file)
        log_and_print("INFO", f"執行計算邏輯: 成功")
        return True
    except Exception as e:
        log_and_print("ERROR", f"處理過程中出現例外: {type(e).__name__}: {e}")
        return False

# ============ 模組 4: 重命名與輸出 ============
def output_file(temp_file, original_info):
    """生成輸出檔案（帶日期戳）"""
    try:
        # 生成輸出檔名
        today = datetime.now().strftime("%y%m%d")
        name_without_ext, ext = os.path.splitext(original_info["source_file"])
        output_filename = f"{os.path.basename(name_without_ext)}_{today}{ext}"
        output_path = os.path.join(OUTPUT_DIR, output_filename)
        
        # 檢查是否已存在（用於覆蓋前記錄）
        if os.path.exists(output_path):
            old_mtime = os.stat(output_path).st_mtime
            log_and_print(
                "WARNING",
                f"輸出檔案已存在，將被覆蓋: {output_path} (舊版本修改時間: {old_mtime})"
            )
        
        # 移動到輸出位置
        shutil.move(temp_file, output_path)
        log_and_print("INFO", f"輸出檔案: {output_filename}")
        
        # 驗證輸出檔案
        if os.path.exists(output_path):
            output_size = os.path.getsize(output_path)
            log_and_print("INFO", f"輸出檔案驗證: 成功 (大小: {output_size} bytes)")
            return output_path
        else:
            log_and_print("ERROR", f"輸出檔案驗證失敗")
            return None
    except Exception as e:
        log_and_print("ERROR", f"輸出檔案保存失敗: {e}")
        return None

# ============ 模組 5: 驗證與日誌 ============
def verify_and_finalize(original_info):
    """驗證原始文件未被修改，輸出最終狀態"""
    try:
        current_stat = os.stat(original_info["source_file"])
        current_size = current_stat.st_size
        current_mtime = current_stat.st_mtime
        
        if (original_info["original_size"] != current_size or
            original_info["original_mtime"] != current_mtime):
            log_and_print(
                "ERROR",
                f"原始文件已被修改！大小：{original_info['original_size']} → {current_size}"
            )
            print("系統通知：原始文件意外修改！")
            return False
        else:
            log_and_print("INFO", f"原始文件驗證: 完整未改變")
            return True
    except Exception as e:
        log_and_print("ERROR", f"驗證失敗: {e}")
        return False

# ============ 主流程 ============
def main():
    """執行完整的文件處理流程"""
    
    # 模組 1: 初始化
    original_info = initialize()
    if not original_info:
        return
    
    # 模組 2: 複製
    temp_file = copy_file(original_info)
    if not temp_file:
        return
    
    # 模組 3: 處理
    if not process_file(temp_file):
        return
    
    # 模組 4: 輸出
    output_path = output_file(temp_file, original_info)
    if not output_path:
        return
    
    # 模組 5: 驗證
    if verify_and_finalize(original_info):
        log_and_print("INFO", f"處理完成: 成功")
        print(f"✓ 成功！輸出檔案位置：{output_path}")
    else:
        log_and_print("ERROR", f"處理完成: 失敗")

if __name__ == "__main__":
    main()
