# Cowork Skill 倉庫

個人 Cowork skill 的版本控管倉庫（私人 repo）。只存放 skill 本身（說明文件、腳本、測試情境），不含任何使用 skill 處理過的資料。

## 結構

```
skills/      自建 skill
forks/       取自開源專案的 skill（保留原授權檔）
MEMORY.md    決策紀錄
ERRORS.md    試錯紀錄
```

## 自建 skill（skills/）

| Skill | 用途 |
|---|---|
| chart-generator | CSV／Excel 資料轉高管級 PPTX 原生圖表 |
| chart-from-text | 中文文字中的數據轉 PNG 圖表 |
| presentation-generator | 上傳檔案轉公司格式 PPTX（Q1~Q5 問答流程） |
| docx-reference-format | Word 文字外觀比照範本、圖表版面鎖定原始檔；多章節格式稽核 |
| docx-anchor-image-layout | 修正 Word 浮動錨點圖片位置、尺寸、分節符號 |
| file-automation-framework | 檔案批次處理前置規範：原檔保護、日期命名、錯誤處理 |
| pdf-to-jpeg | PDF 逐頁轉 JPEG |
| quarterly-ohs-law-compliance-check | 每季職安衛法規查核與紀錄表產出 |
| mac-health-check | M1 MacBook Pro 資源、硬碟、電池健康檢查 |
| route-navigator | 開車／重機／大眾運輸導航，附 Apple 與 Google 地圖連結 |
| transit-route-links | 旅行時大眾運輸路線查詢（已由 route-navigator 取代） |
| hotel-search | Amex FHR 與 IHG 飯店房價與會員福利查詢 |
| webforms-playwright-scraper | ASP.NET WebForms 內部系統的 Playwright 爬蟲建置 |

## 開源 skill（forks/）

| Skill | 來源 | 用途 |
|---|---|---|
| prompt-master | github.com/nidhinjs/prompt-master | 為各種 AI 工具產生最佳化提示詞 |

## 遮蔽說明

個人姓名與公司資料夾路徑已替換為 `~/` 與 `<公司名稱>`。實際使用中的 skill 不受影響；若要從本倉庫還原安裝，需將佔位符改回實際路徑。
