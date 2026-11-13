---
name: presentation-generator
description: 將上傳的檔案內容轉換成專業 PPTX。當使用者說「做週報」、「整理週報」、「製作廠務處工作報告」、「工作回報」、「生成演示文稿」、「報告 PPT」、「高管匯報」或將任意文件（PDF/Word/Excel/圖片）轉成 PPTX 時使用。採用 Q1~Q5 五問詢問工作流：Q1 版本深度（簡介／標準／詳述）、Q2 投影片尺寸、Q3 黃色 Banner、Q4 設計風格、Q5 合併 PPTX。依來源文件的主題順序呈現，每個主題下套用「背景、數據、流程、結論」四個維度（缺則跳過）。偵測到數值資料需視覺化時自動聯動 chart-generator；選擇創意藝術風格時完成 PPTX 後調用 canvas-design。
---

# 簡報生成 Skill

將各種檔案格式的內容轉換成專業的 PPTX。
**全模式統一字體：思源黑體 (Noto Sans TC)**

---

## Step 1 — 啟動詢問 (Q1 ~ Q5，逐題對答)

使用者上傳檔案後，**依序逐題提問，每題等待使用者回覆後再問下一題，不得一次拋出所有問題。**

**Q1（第一題）：**
> 「收到您的檔案。請問要製作哪個版本？
> (A) 簡介版（1–2 頁）：重點摘要，適合快速過場報告
> (B) 標準版（3–5 頁）：完整說明，適合一般週會或常規匯報
> (C) 詳述版（6 頁以上）：詳細分析，適合需要深入討論的議題」

→ **等待回覆後**，再提問 Q2：

**Q2：**
> 「投影片大小？
> (A) 16:9（預設）
> (B) 4:3」

→ **等待回覆後**，再提問 Q3：

**Q3：**
> 「是否套用黃色 Banner？
> (A) 是（強制於每頁頂部加上標準黃色 Banner）
> (B) 否」

→ **等待回覆後**，再提問 Q4：

**Q4：**
> 「設計風格？
> (A) 預設（中性專業，平鋪直述）
> (B) 創意藝術（生成後將調用 canvas-design 補強視覺元素）
> (C) 上傳範例（請上傳參考檔案，我將模仿其排版與圖文比例）」

→ **等待回覆後**，再提問 Q5：

**Q5：**
> 「是否有需要合併的其他報告 (PPTX)？
> (A) 是（請一併上傳，會接續在最後一頁）
> (B) 否」

→ **Q5 回覆收到後**，五題全部確認完畢，繼續進行 Step 2。

> ⚠️ 版本由 Q1 統一決定。後續呼叫 chart-generator 時直接帶入，不再詢問。

---

## Step 2 — 讀取來源文件與主題分類

依檔案類型提取內容：

| 類型 | 工具 |
|------|------|
| `.pptx` | `extract-text` |
| `.docx` | `python-docx` / `mammoth` |
| `.xlsx` | `openpyxl`（保留數值與欄位結構） |
| `.pdf` | `pdfminer` / `pymupdf` |

**依來源文件的主題順序**識別各主題，不重新排序、不強制歸類。

針對每個主題，評估以下四個維度是否存在（缺則跳過，不補充）：

| 維度 | 說明 |
|------|------|
| **背景** | 主題的目的、脈絡、前提說明 |
| **數據** | 可量化的數值、圖表、統計資料 |
| **流程** | 執行步驟、進度、操作程序 |
| **結論** | 結果、建議、待辦事項 |

```
主題內含結構化數值資料？（Excel 數值欄位、產量/成本/進度數字表格）
  └─ 是 → 標記為「圖表類」→ Step 3 呼叫 chart-generator
  └─ 否 → 標記為「簡報類」→ Step 4 直接生成

同一主題若同時含文字說明與數據：
  → 文字部分走 Step 4，數據部分走 Step 3
  → 圖表以 PNG 形式嵌入對應投影片
```

---

## Step 3 — 圖表類內容：呼叫 chart-generator（手動中繼）

閱讀 `chart-generator` SKILL.md，依其流程執行。帶入 Q1 版本（跳過版本問答）：

| Q1 版本 | chart-generator 對應規格 |
|---------|------------------------|
| 簡介版 | 單一圖表，精簡標注 |
| 標準版 | 圖表 + 補充數據表 |
| 詳述版 | 多張圖表拆分不同維度 |

> 「圖表已在 Canva 生成，請開啟以下連結，點選「下載」→「PNG」後將檔案上傳回來，我會將圖片插入對應的投影片。
> 🔗 [Canva 設計連結]」

**等待使用者上傳 PNG 後再繼續。**

圖片嵌入規格：
- 寬度：內容區滿版（w = 9.2 英吋）；高度等比縮放
- 位置：Banner 下方（若 Q3 為「是」），水平置中（x = 0.4, y = 0.65）
- 每張圖表對應一張投影片，投影片標題為該圖表的主題名稱

---

## Step 4 — 投影片生成與格式規範

依據 Step 1 的問答結果生成 PPTX：

### 頁數控制（Q1）

| 版本 | 每個主題的投影片數 | 說明 |
|------|-----------------|------|
| 簡介版 | 1 頁 | 僅呈現最核心的重點，略去細節 |
| 標準版 | 1–2 頁 | 完整呈現各維度，適量展開 |
| 詳述版 | 2–3 頁 | 各維度充分展開，含輔助說明 |

> ⚠️ 封面頁與結束頁不計入頁數限制。

### 通用格式規範

- **字體**：全面且唯一使用「**思源黑體 (Noto Sans TC)**」
- **封面頁**：有（含報告名稱、日期）
- **結束頁**：有
- **頁碼**：右下角，10pt
- **Bullet Points**：無法轉化為圖表的細節，強制提煉為精煉 Bullet Points，**嚴禁大段落文字**

### 投影片尺寸（Q2）

```javascript
const pptx = new PptxGenJS();
// (A) 16:9
pptx.layout = 'LAYOUT_WIDE';
// (B) 4:3
pptx.layout = 'LAYOUT_4x3';
```

### 黃色 Banner（Q3）

選「是」→ 每頁加上固定規格之黃色 Banner：

| 屬性 | 數值 |
|------|------|
| x | 0.6688 英吋 |
| y | 0.18 英吋 |
| w | 8.7411 英吋（16:9）/ 依 4:3 等比調整 |
| h | 0.6562 英吋 |
| 背景色 | `#FFFF00`（純黃） |
| 字型 | 思源黑體 (Noto Sans TC) |
| 字級 | 32pt Bold |
| 文字色 | `#000000` |
| 對齊 | 水平置中、垂直置中 |

```javascript
slide.addShape(pptx.shapes.RECTANGLE, {
  x: 0.6688, y: 0.18, w: 8.7411, h: 0.6562,
  fill: { color: 'FFFF00' }, line: { color: 'FFFF00' }
});
slide.addText(title, {
  x: 0.6688, y: 0.18, w: 8.7411, h: 0.6562,
  align: 'center', valign: 'middle',
  fontSize: 32, bold: true, color: '000000',
  fontFace: 'Noto Sans TC'
});
```

選「否」→ 無 Banner。

### 設計風格（Q4）

- **A（預設）**：背景單色，無多餘裝飾
- **B（創意藝術）**：PPTX 基礎版面完成後，觸發調用 `canvas-design` 強化視覺與配色。必須先完成 PPTX 再調用，不得提前
- **C（上傳範例）**：分析使用者上傳之參考檔案，模仿其轉場邏輯、區塊分割與視覺平衡感

---

## Step 5 — 合併報告處理（Q5）

若 Q5 選擇「是」：

- 讀取使用者上傳的合併 PPTX，附加至本次生成簡報的最末端
- **Banner 處理（依 Q3）**：
  - **Q3 為「是」** → 合併進來的投影片頂端，**強制覆蓋加上標準黃色 Banner**

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
import copy

BANNER_X, BANNER_Y = Inches(0.6688), Inches(0.18)
BANNER_W, BANNER_H = Inches(8.7411), Inches(0.6562)

def append_slides_with_banner(base_prs, append_path, slide_title=""):
    append_prs = Presentation(append_path)
    for slide in append_prs.slides:
        layout = base_prs.slide_layouts[0]
        new_slide = base_prs.slides.add_slide(layout)
        new_slide.shapes._spTree[:] = []
        for shape in slide.shapes:
            new_slide.shapes._spTree.append(copy.deepcopy(shape._element))
        bg = new_slide.shapes.add_shape(1, BANNER_X, BANNER_Y, BANNER_W, BANNER_H)
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0x00)
        bg.line.color.rgb = RGBColor(0xFF, 0xFF, 0x00)
        tf = new_slide.shapes.add_textbox(BANNER_X, BANNER_Y, BANNER_W, BANNER_H)
        p = tf.text_frame.paragraphs[0]
        p.alignment = 2
        run = p.add_run()
        run.text = slide_title
        run.font.name = 'Noto Sans TC'
        run.font.size = Pt(32)
        run.font.bold = True
        run.font.color.rgb = RGBColor(0, 0, 0)
    return base_prs
```

  - **Q3 為「否」** → 直接接在最後頁之後，**不做任何編輯與排版更動**（保持原檔案樣貌）

---

## Step 6 — QA 與輸出

```bash
python scripts/office/soffice.py --headless --convert-to pdf output.pptx
pdftoppm -jpeg -r 150 output.pdf slide
ls -1 "$PWD"/slide-*.jpg
```

輸出至 `/mnt/user-data/outputs/`，使用 `present_files` 提供下載。

**檔名規則：** `[報告名稱]_YYYYMMDD.pptx`

---

## 遇到不確定時的處理

立即停下並提問，不要自作聰明補充：

- 原檔案內容模糊 → 「檔案中這部分說的是 X 還是 Y？」
- 數據衝突 → 「Excel 的 Q3 數據是 100 還是 120？我看到兩個不同數字。」
- 缺失信息 → 「檔案沒有提到[關鍵概念]，我應該：A)跳過 B)用通用表述 C)等你提供？」
- 格式衝突 → 「原檔案中這個表格有 15 列，PPTX 一頁放不下，我應該怎麼處理？」

---

## 品質保證清單

**通用：**
- ✓ 所有內容 100% 來自上傳檔案（無補充）
- ✓ 全文字體皆為「思源黑體 (Noto Sans TC)」
- ✓ 已確實完成 Q1~Q5 的詢問並取得答案
- ✓ 來源文件的主題順序未被變動
- ✓ 每個主題僅呈現存在的維度（背景/數據/流程/結論），不補充空維度
- ✓ 沒有遺漏原檔案中的關鍵數據

**Banner（Q3 為「是」）額外確認：**
- ✓ 每頁均有 Banner（位置、尺寸、黃色背景完全符合規格）
- ✓ 合併 PPTX（如有）已在每張頂端強制覆蓋標準黃色 Banner

**圖表聯動額外確認：**
- ✓ chart-generator PNG 已正確嵌入（位置、尺寸符合規格）
- ✓ Q1 版本深度已帶入 chart-generator（不重複詢問）

**創意藝術（Q4 為「B」）額外確認：**
- ✓ canvas-design 已在 PPTX 完成後補上創意視覺元素

---

## 使用提示

- **Q1 未回覆** → 預設標準版（B）
- **Q2 未回覆** → 預設 16:9（A）
- **Q4 未回覆** → 預設中性專業（A）
- **上傳格式不標準** → 提前告知可能的相容性問題
- **chart-generator 聯動** → 輸出為 Canva 連結，必須先匯出 PNG 才能嵌入 PPTX
- **canvas-design 聯動** → 僅 Q4 選擇「B — 創意藝術」時才調用
