---
name: chart-generator
description: 從 CSV、Excel 等資料檔案自動生成高管級別的專業圖表，直接輸出 PPTX 原生圖表投影片。觸發場景：使用者上傳資料檔案（CSV/Excel）並要求視覺化生產效率、成本對比、品質指標等業務數據。智慧選擇最適合的圖表類型（直條、折線、混合）。獨立使用時，第 0 步詢問設計風格與版面參考；由其他 skill 呼叫時跳過詢問，固定使用中性專業並依傳入參數控制 Banner。使用時機：任何涉及資料檔案轉圖表、業務指標視覺化、成本分析、品質追蹤、或為報告/簡報生成專業圖表的請求。
---

# Chart Generator Skill（python-pptx 原生圖表版）

為高階主管決策用途，從結構化數據生成可在 PowerPoint 內編輯的原生圖表投影片。

> **版本說明**：v2.3 — 新增 `add_banner` 參數，解決 presentation-generator 聯動時的雙 Banner 衝突。

---

## 呼叫介面說明

```
獨立使用：        banner 由第 0 步 Q1 控制，預設 add_banner=True
被其他 skill 呼叫：呼叫方傳入 add_banner=True/False，跳過第 0 步詢問
```

| 呼叫方 | add_banner 值 | 說明 |
|--------|--------------|------|
| 獨立使用 | `True`（預設） | 圖表投影片自帶 Banner |
| presentation-generator（任何 Q3） | `False` | Banner 完全由 presentation-generator 負責；chart-generator 不介入，圖表延伸至頂部 |

> ⚠️ **核心原則**：`add_banner` 是**呼叫方的責任宣告**，不是 Q3 狀態的映射。
> presentation-generator 無論 Q3=是或否，呼叫 chart-generator 時一律傳入 `False`；
> Q3 的結果只影響 presentation-generator 自身的投影片處理，與 chart-generator 無關。

---

## 工作流程

### 第 0 步：詢問設計風格與版面參考（獨立使用時）

> ⚠️ **由其他 skill 呼叫時**：跳過此步驟，直接進入第 1 步，固定使用「中性專業」模式。

依序逐題提問，**每題等待使用者回覆後再提出下一題**：

**Q1：設計風格**
```
請選擇設計風格：
A. 中性專業（內定）— python-pptx 原生圖表，PowerPoint 內可直接編輯數據
B. 創意藝術 — 調用 canvas-design skill，輸出為 PNG，PowerPoint 內不可編輯數據
```
→ 收到回覆後記錄，進入 Q2。

**Q2：版面參考**
```
是否提供 Design_Template.pdf 作為版面佈局參考？
A. 否（內定）— 採用內建高管標準版面
B. 是 — 請上傳 PDF，系統將分析其版面結構並套用至圖表佈局邏輯
```
→ 若選 B，等待使用者上傳 PDF 後再進入 Q3；若選 A 直接進入 Q3。

**Q3：是否加上黃色 Banner**
```
是否在投影片頂部加上黃色標題 Banner？
A. 是（內定）— 標準黃色 Banner 承載圖表標題
B. 否 — 無 Banner，圖表延伸至頂部
```
→ 收到回覆後，依以下規則分流執行：

- **Q1 = A**：進入第 4A 步（中性專業）
- **Q1 = B**：進入第 4B 步（創意藝術）
- **Q2 = B**：在第 2 步前先執行 PDF 版面分析
- **Q3 = A**：`add_banner=True`
- **Q3 = B**：`add_banner=False`，圖表座標自動切換至無 Banner 版面

---

### PDF 版面分析（Q2 = 是時執行）

使用 `pdf` skill 讀取上傳的 PDF，提取以下資訊：

```
分析目標：
├─ 資訊層級：標題 / 副標 / 圖表 / 補充文字的層次與比例
├─ 佈局分割：圖表佔版面的寬高比例
├─ 視覺密度：留白比例（判斷是否符合 20–30% 目標）
└─ 數據呈現邏輯：圖表類型偏好、數值標示方式、圖例位置
```

分析結果覆蓋 LAYOUT_MODE 與 CHART_RATIO（第 4A 步使用）。

---

### 第 1 步：資料讀取與驗證

```python
import pandas as pd

def read_data(file_path):
    if file_path.endswith(('.xlsx', '.xls')):
        xf = pd.ExcelFile(file_path)
        if len(xf.sheet_names) > 1:
            return None, xf.sheet_names
        df = pd.read_excel(file_path, sheet_name=0)
    else:
        df = pd.read_csv(file_path, encoding='utf-8-sig')
    return df, None
```

**資料驗證**：欄位數 ≥ 2、數值欄存在、缺失值處理、時間序列自動偵測。

---

### 第 2 步：資料分析與圖表類型決策

```
決策樹（優先順序）：
1. 含時間維度 → 折線圖（趨勢追蹤）
2. 數值欄 ≥ 2  → 混合圖（直條＋折線）
3. 分類數 ≤ 8  → 直條圖；否則 → 橫條圖
```

同時判斷是否有無法視覺化的補充資訊：
- 有 → 提取為 Bullet Points，啟用左右分欄版面
- 無 → `LAYOUT_MODE = 'full_width'`
- Bullet Points > 8 條 → 分拆為多張投影片

---

### 第 3 步：資料準備

```python
def prepare_data(df, chart_type):
    df = df.dropna(how='all').dropna(axis=1, how='all').fillna('N/A')
    for col in df.select_dtypes(include='object').columns:
        df[col] = df[col].astype(str).str[:20]
    for col in df.select_dtypes(include='number').columns:
        if df[col].max() >= 100000:
            df[col] = (df[col] / 10000).round(1)
            df = df.rename(columns={col: col + '（萬）'})
    if len(df) > 15:
        df = df.head(12)
    return df
```

---

### 第 4A 步：中性專業 — python-pptx 原生圖表

**安裝依賴**

```bash
pip install python-pptx pandas openpyxl --break-system-packages
```

**版面常數（4:3，10 × 7.5 英吋）**

```python
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE
from pptx.chart.data import ChartData

FONT_PRIMARY = 'Noto Sans TC'

SLIDE_W = Inches(10)
SLIDE_H = Inches(7.5)

# ── Banner 規格 ──────────────────────────────────────────────────
BANNER_X = Inches(0.3)
BANNER_Y = Inches(0.15)
BANNER_W = Inches(9.4)
BANNER_H = Inches(0.65)

# ── 圖表 Y 起點與高度（依 add_banner 決定）──────────────────────
#   add_banner=True ：圖表在 Banner 下方（1.0 英吋起）
#   add_banner=False：圖表從頂部 0.15 英吋起，高度填滿至 7.25 英吋
CHART_Y_WITH_BANNER = Inches(1.0)
CHART_H_WITH_BANNER = Inches(6.0)
CHART_Y_NO_BANNER   = Inches(0.15)
CHART_H_NO_BANNER   = Inches(7.1)   # 底留 0.25 英吋邊距

# ── 左右分欄（有 Bullet Points）────────────────────────────────
CHART_X_SPLIT = Inches(0.3)
CHART_W_SPLIT = Inches(6.2)   # 圖表 ~65%
BULLET_X      = Inches(6.7)
BULLET_W      = Inches(3.0)   # Bullet ~30%，剩餘為留白

# ── 全寬圖表（無 Bullet Points）────────────────────────────────
CHART_X_FULL = Inches(0.3)
CHART_W_FULL = Inches(9.4)
```

**座標解析輔助函式**

```python
def _resolve_coords(add_banner: bool, use_split: bool):
    """依 Banner 狀態與版面模式，回傳 (cx, cy, cw, ch, bullet_y, bullet_h)"""
    cy = CHART_Y_WITH_BANNER if add_banner else CHART_Y_NO_BANNER
    ch = CHART_H_WITH_BANNER if add_banner else CHART_H_NO_BANNER

    if use_split:
        return CHART_X_SPLIT, cy, CHART_W_SPLIT, ch, cy, ch
    else:
        return CHART_X_FULL, cy, CHART_W_FULL, ch, cy, ch
```

**Banner 生成**

```python
def _add_banner(slide, title):
    shape = slide.shapes.add_shape(1, BANNER_X, BANNER_Y, BANNER_W, BANNER_H)
    shape.fill.solid()
    shape.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0x00)
    shape.line.fill.background()

    tf = slide.shapes.add_textbox(BANNER_X, BANNER_Y, BANNER_W, BANNER_H).text_frame
    tf.word_wrap = False
    tf.text = title
    p = tf.paragraphs[0]
    p.alignment = 2
    run = p.runs[0]
    run.font.name  = FONT_PRIMARY
    run.font.size  = Pt(28)
    run.font.bold  = True
    run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)
```

**主圖表生成**

```python
def create_chart_slide(df, chart_type, title, category_col, value_cols,
                        bullet_points=None, add_banner=True):
    """
    add_banner   : True  → 投影片自帶 Banner（獨立使用預設）
                   False → 無 Banner，圖表延伸至頂（由呼叫方管理 Banner）
    bullet_points: list[str] | None → 有值則啟用左右分欄
    """
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    if add_banner:
        _add_banner(slide, title)

    use_split = bool(bullet_points)
    cx, cy, cw, ch, bullet_y, bullet_h = _resolve_coords(add_banner, use_split)

    chart_data = ChartData()
    chart_data.categories = df[category_col].astype(str).tolist()
    for col in value_cols:
        chart_data.add_series(col, df[col].tolist())

    chart_type_map = {
        'bar':        XL_CHART_TYPE.COLUMN_CLUSTERED,
        'horizontal': XL_CHART_TYPE.BAR_CLUSTERED,
        'line':       XL_CHART_TYPE.LINE_MARKERS,
    }
    xl_type = chart_type_map.get(chart_type, XL_CHART_TYPE.COLUMN_CLUSTERED)

    chart = slide.shapes.add_chart(xl_type, cx, cy, cw, ch, chart_data).chart
    apply_chart_style(chart)

    if use_split:
        _add_bullet_panel(slide, bullet_points, bullet_y, bullet_h)

    return prs


def create_mixed_chart_slide(df, title, category_col, bar_col, line_col,
                              bullet_points=None, add_banner=True):
    prs = Presentation()
    prs.slide_width  = SLIDE_W
    prs.slide_height = SLIDE_H
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    if add_banner:
        _add_banner(slide, title)

    use_split = bool(bullet_points)
    cx, cy, cw, ch, bullet_y, bullet_h = _resolve_coords(add_banner, use_split)

    chart_data = ChartData()
    chart_data.categories = df[category_col].astype(str).tolist()
    chart_data.add_series(bar_col,  df[bar_col].tolist())
    chart_data.add_series(line_col, df[line_col].tolist())

    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED, cx, cy, cw, ch, chart_data
    ).chart
    chart.plots[0].series[1].chart_type = XL_CHART_TYPE.LINE_MARKERS
    apply_chart_style(chart)

    if use_split:
        _add_bullet_panel(slide, bullet_points, bullet_y, bullet_h)

    return prs
```

**輔助函式**

```python
def _add_bullet_panel(slide, bullet_points, bullet_y, bullet_h):
    tf = slide.shapes.add_textbox(BULLET_X, bullet_y, BULLET_W, bullet_h).text_frame
    tf.word_wrap = True
    for i, point in enumerate(bullet_points):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_before = Pt(8)
        run = p.add_run()
        run.text = f'• {point}'
        run.font.name  = FONT_PRIMARY
        run.font.size  = Pt(11)
        run.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)


def apply_chart_style(chart):
    PRIMARY   = RGBColor(0x1E, 0x40, 0xAF)
    SECONDARY = RGBColor(0xDC, 0x26, 0x26)
    plot = chart.plots[0]
    for i, series in enumerate(plot.series):
        series.format.fill.solid()
        series.format.fill.fore_color.rgb = PRIMARY if i == 0 else SECONDARY
    chart.has_title  = False
    chart.has_legend = (len(list(plot.series)) > 1)
    for axis in [chart.value_axis, chart.category_axis]:
        try:
            axis.tick_labels.font.name = FONT_PRIMARY
            axis.tick_labels.font.size = Pt(10)
        except Exception:
            pass
    chart.value_axis.major_gridlines.format.line.color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
```

---

### 第 4B 步：創意藝術 — canvas-design + PNG 嵌入

閱讀 `canvas-design` SKILL.md 依其流程執行。PNG 儲存至 `/home/claude/charts/chart_creative.png`。

嵌入 PPTX 時：
- `add_banner=True` → 先呼叫 `_add_banner()`，圖片從 `CHART_Y_WITH_BANNER` 起
- `add_banner=False` → 跳過 Banner，圖片從 `CHART_Y_NO_BANNER` 起，填滿 `CHART_H_NO_BANNER`

設計提示給 canvas-design：字型 Noto Sans TC、語氣中性專業、嚴禁裝飾性元素、留白 20–30%。

---

### 輸出

```python
output_path = '/mnt/user-data/outputs/chart_[主題名稱].pptx'
prs.save(output_path)
# 備註：若 Noto Sans TC 未安裝，PowerPoint 將自動替換字型。
```

---

## 版面規範（高管級別）

| 項目 | 規範 |
|------|------|
| 投影片尺寸 | 4:3（10 × 7.5 英吋） |
| 背景 | 純白 `#FFFFFF` |
| 主色 | 深藍 `#1E40AF` |
| 次色 | 深紅 `#DC2626` |
| 文字色 | 深灰 `#1F2937` |
| 字型 | **Noto Sans TC（思源黑體）**，統一全投影片 |
| 標題 | Banner 承載（28pt Bold），圖表本身不顯示標題 |
| 標籤 / Bullet | 11pt regular |
| 留白 | 嚴格執行 20–30%；資訊過載時分拆頁面，嚴禁壓縮 |
| 版面模式 | 有補充文字 → 左右分欄（圖表 65% / Bullet 30% / 留白 5%）<br>無補充文字 → 全寬圖表 |
| Banner 控制 | `add_banner` 參數化；獨立使用預設 True，被呼叫時由呼叫方決定 |
| 視覺元素 | 嚴格對應來源數據，嚴禁添加無關裝飾性物件 |
| 資訊準確性 | 100% 映射來源數據，嚴禁遺漏 |

---

## 常見問題處理

| 問題 | 處理方案 |
|------|----------|
| 缺失值 | 折線圖斷開；直條圖跳過該分類 |
| 資料超大（> 1000 行） | 提示篩選，最多保留 12 行 |
| 超長分類名 | 自動截斷至 ≤ 15 字元 |
| 多 Sheet 檔案 | 列出清單等使用者選擇 |
| 時間格式混亂 | 嘗試多種解析格式；失敗則提示 |
| 無標題提供 | 從主要數值欄名稱推導 |
| 資訊量過大 | 分拆多張投影片，嚴禁壓縮 |
| Design_Template.pdf 未上傳 | 採用內建版面規範，流程繼續 |
| Noto Sans TC 未安裝 | 輸出備註提醒 |

---

## 版本說明

- **v1.0**：Canva API 版（已棄用）
- **v2.0**：python-pptx 原生圖表
- **v2.1**：設計風格選項（中性專業 / 創意藝術）
- **v2.2**：Noto Sans TC、左右分欄版面、PDF 參考選項
- **v2.3**（當前）：
  - `add_banner` 參數化，解決 presentation-generator 聯動時的雙 Banner 衝突
  - `_resolve_coords()` 統一管理有/無 Banner 時的圖表座標
  - Banner 由最上層呼叫方決定，chart-generator 不做假設
