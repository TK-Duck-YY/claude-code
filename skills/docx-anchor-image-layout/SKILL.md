---
name: docx-anchor-image-layout
description: 修正 Word (.docx) 文件中浮動錨點圖片（wp:anchor）的版面問題，包含圖片尺寸、位置（posH/posV）、空段落數、分節符號清除。適用場景：圖片位置跑掉、圖片與標題不在同一頁、頁面出現「分節符號(下一頁)」標記、橫向校正報告圖片偏移、空白頁異常增多、直向圖片高度不一致。觸發關鍵詞：「圖片跑掉」「posV posH 異常」「分節符號搗亂」「空白頁」「橫向圖置中」「直向圖統一高度」「排版跑掉」「圖片和標題不同頁」「圖片位置」「section break」。與 docx-reference-format 連動使用時，請先執行 docx-reference-format（修文字外觀），再執行本 skill（修圖片版面）。
---

# docx-anchor-image-layout

修正 Word 浮動錨點圖片版面，不動文字外觀、不動頁首頁尾。

## 文件前提知識

此 skill 適用於圖片為 **`wp:anchor`**（浮動錨點）型別的文件，而非 `wp:inline`（內嵌）。

**預設版面規則（可透過參數調整）：**

| 類型 | 判斷條件 | 目標尺寸 | posH | posV |
|------|---------|---------|------|------|
| 直向大圖 | cy > cx 且 cy ≥ 18 cm | 高度 22.6 cm（等比縮寬） | 1.241 cm from column | 0.500 cm from paragraph |
| 橫向大圖 | cx ≥ cy 且兩者 ≥ 10 cm | 不改尺寸 | 頁面置中（page center） | 0.500 cm from paragraph |

**空段落規則：** 每張直向大圖後需有 4 個空段落，以填滿頁面底部餘白（26.99 cm 頁面，圖底 23.1 cm，餘 ~3.89 cm）。

**分節符號問題：** H4 段落上的 `sectPr`（分節）會在 Word 中顯示為「════分節符號(下一頁)════」可見標記；用 `pageBreakBefore`（段落前分頁屬性）取代後，分頁效果相同但標記不可見。

---

## 執行步驟

### Step 1：確認輸入

詢問使用者：
- 原始 `.docx` 路徑
- 輸出路徑（預設：原名 + `_fixed`）
- 前段是否已手動排版？（若是，詢問大約從哪個頁面起）
- 是否有可見的「分節符號」標記要清除？（決定是否加 `--fix-sect`）

### Step 2：執行腳本

腳本路徑：`scripts/fix_anchor_images.py`

**標準執行（修圖片尺寸 + 位置 + 空段落）：**
```bash
python scripts/fix_anchor_images.py "輸入.docx" "輸出.docx"
```

**同時清除分節符號（圖片段落有「分節符號」標記時）：**
```bash
python scripts/fix_anchor_images.py "輸入.docx" "輸出.docx" --fix-sect
```

**前段已手動排版，只處理後半段（以第 195 個 body element 起為例）：**
```bash
python scripts/fix_anchor_images.py "輸入.docx" "輸出.docx" --start-body 195 --fix-sect
```

### Step 3：回報統計

執行後讀取腳本輸出，向使用者回報修正摘要（修了幾張圖、加/刪幾個空段落、清了幾個 sectPr）。

---

## 完整參數說明

```
圖片幾何：
  --portrait-height CM   直向大圖目標高度（預設 22.6 cm）
  --portrait-posv   CM   直向大圖 posV from paragraph（預設 0.500 cm）
  --portrait-posh   CM   直向大圖 posH from column（預設 1.241 cm）
  --landscape-posv  CM   橫向大圖 posV from paragraph（預設 0.500 cm）
  --portrait-min    CM   直向大圖最小高度門檻（預設 18.0 cm）
  --landscape-min   CM   橫向大圖最小尺寸門檻（預設 10.0 cm）

空段落：
  --empty-paras N        直向大圖後空段落數（預設 4）

執行範圍：
  --start-body N         從第 N 個 body element 開始（前段已手動排好時用）

模式開關：
  --fix-sect             清除 H3/H4 的 sectPr → pageBreakBefore
  --no-fix-images        跳過圖片幾何修正
  --no-fix-paras         跳過空段落標準化
```

---

## 常見症狀 → 診斷 → 處置

| 症狀 | 原因 | 處置 |
|------|------|------|
| 圖片出現在標題下方很遠（大空白） | posV 太大（如 7.19 cm） | 預設修正到 0.500 cm |
| 橫向圖偏左偏右 | posH 未置中 | 自動改為 page center |
| 每張圖後多出空白頁 | 空段落帶 sectPr | `--fix-sect` |
| 圖片標題出現在頁面底部、圖在頁中 | H4 的 sectPr 讓錨點跑到頁底 | `--fix-sect` |
| H3 標題獨佔一頁 | H3 有 sectPr | `--fix-sect`（自動移除 H3 sectPr） |
| 「═══分節符號(下一頁)═══」可見標記 | H4 段落有 sectPr | `--fix-sect` |
| 前段（如第 1-37 頁）已正確，後段跑掉 | 手動排版範圍外未套用規則 | `--start-body N` |

---

## 與 docx-reference-format 的連動

兩個 skill 分工不重疊，可安全串接：

```
① docx-reference-format
   → 修文字外觀（字型/字級/顏色/段落間距）
   → 修 word/styles.xml、word/numbering.xml

② docx-anchor-image-layout（本 skill）
   → 修圖片版面（尺寸/posH/posV/分頁結構）
   → 修 w:drawing 錨點幾何、w:sectPr、空段落
```

執行順序：先 ①，再 ②，兩者都不觸碰對方的管轄範圍。

---

## 已知限制

- 僅處理 `wp:anchor` 浮動圖片；`wp:inline` 內嵌圖片不在範圍內。
- `--fix-sect` 的序列分組邏輯：兩個 H4 之間若夾有 H3，視為不同序列（各自獨立處理）。
- 空段落計算以 `w:p`（無文字、無圖片）為準；若空段落帶有格式設定仍會被計入。
- 頁面高度 26.99 cm、4 個空段落 ≈ 3.89 cm 是根據特定邊界設定推算的預設值，不同文件可能需要調整 `--empty-paras`。
