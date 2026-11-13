---
name: chart-from-text
description: 從中文文字內容（報告段落、條列式數據、表格描述、週報摘要）自動提取數據，判斷最適合的圖表類型，並輸出為 PNG 圖片檔案。使用者有文字描述的數據但沒有結構化檔案時使用此 skill。也可被 presentation-generator 呼叫，為投影片生成 PNG 圖表素材。只要看到「幫我做成圖表」、「視覺化這份資料」、「把這段數據做成圖」、「製作圖表」、「用圖表呈現」等請求，或使用者貼入含有數值的中文文字並暗示想要圖表化，立即觸發此 skill。
---

# Chart from Text Skill

從中文文字內容智慧提取數據，自動選擇圖表類型，生成專業商務 PNG 圖表。

---

## 呼叫介面

**獨立使用**：使用者直接貼入文字內容，Claude 分析後自動生成圖表。

**被 presentation-generator 呼叫**（以 `[CHART-FROM-TEXT]` 標記）：

```
[CHART-FROM-TEXT]
內容：<文字描述或數據段落>
輸出路徑：<指定 PNG 檔名，例如 chart_yield.png>
標題：<圖表標題>（選填）
圖表類型：<指定類型>（選填，留空則自動判斷）
```

---

## 工作流程

### 第 1 步：分析文字，決定圖表類型

仔細閱讀使用者提供的文字，識別數據結構後依以下決策樹選擇圖表：

| 情境 | 圖表類型 |
|------|---------|
| 含時間序列（週/月/日/季）且只有一組數據 | 折線圖 |
| 含時間序列且有兩組數據（如產量+良率） | 混合圖（直條+折線） |
| 不同類別數值比較（≤8 類） | 直條圖 |
| 不同類別數值比較（>8 類或名稱較長） | 橫條圖 |
| 各部分佔整體比例（≤6 項） | 圓餅圖 |
| 各部分佔整體比例（>6 項） | 甜甜圈圖（顯示前 5 大，其餘合併為「其他」） |
| 多個維度的評分或達成率比較 | 雷達圖 |
| 矩陣式交叉比較（如班次×產線） | 熱力圖 |

提取出：
- **類別標籤**（x 軸或圓餅扇區名稱）
- **數值**（y 軸，含單位）
- **時間軸**（如果有）
- **建議標題**（從文字語意推導）

用一句話告知使用者選了哪種圖表及原因，然後直接執行（被呼叫時跳過此說明）。

> 若文字中數值不明確或有歧義，先詢問確認後再生成，不可猜測數值。

---

### 第 2 步：生成 PNG 圖表

動態撰寫並執行 Python 程式碼，依第 1 步決定的圖表類型生成圖表。

#### 必備標準開頭（每次都要加）

```python
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

plt.rcParams['font.sans-serif'] = ['Heiti TC', 'PingFang TC', 'Arial Unicode MS', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False
matplotlib.rcParams['font.family'] = 'sans-serif'
```

#### 圖表規格

| 項目 | 規格 |
|------|------|
| 尺寸 | `figsize=(10, 6)`；圓餅/甜甜圈 `(8, 8)`；熱力圖依矩陣大小 |
| DPI | `dpi=150` |
| 背景 | 白色 `#FFFFFF` |
| 主色系 | `['#1E40AF', '#DC2626', '#D97706', '#059669', '#7C3AED', '#DB2777']` |
| 標題 | 14pt Bold，顏色 `#1F2937`，使用 `plt.title()` |
| 軸標籤 | 11pt，顏色 `#374151`，含單位（例：「產量（件）」「良率（%）」） |
| 數值標籤 | 9pt，長條圖在頂端，圓餅在扇區內，折線在資料點旁 |
| 格線 | `grid(True, alpha=0.3, linestyle='--')`（僅有數值軸的圖表） |
| 圖例 | 多組數據時顯示，`loc='best'` |

#### 達標/未達標配色（有目標值時）

```python
# 有目標線時，長條/折線資料點依達標與否變色
達標色 = '#059669'  # 綠色
未達標色 = '#DC2626'  # 紅色
目標線色 = '#F59E0B'  # 橘黃，虛線 linestyle='--'
```

#### 長條圖數值標籤範本

```python
for bar in bars:
    height = bar.get_height()
    ax.annotate(f'{height:,}',
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha='center', va='bottom', fontsize=9)
```

#### 折線圖標記形狀（黑白列印相容）

```python
markers = ['o', 's', '^', 'D', 'v', 'P']  # 多組數據時依序套用
```

#### 圓餅圖紋理（黑白列印相容）

```python
hatches = ['', '///', '...', 'xxx', '\\\\\\', '+++']
```

#### 輸出（固定格式）

```python
output_path = 'chart_output.png'  # 被呼叫時替換為指定路徑
plt.tight_layout()
plt.savefig(output_path, dpi=150, bbox_inches='tight',
            facecolor='white', edgecolor='none')
plt.close()
print(f"PNG 圖表已儲存：{output_path}")
```

---

### 第 3 步：回報結果

**獨立使用時**：
- 告知 PNG 完整路徑
- 一句話描述圖表呈現內容
- 詢問是否需要調整（標題、配色、數值格式、圖表類型）

**被 presentation-generator 呼叫時**：輸出以下格式，不問後續問題：

```
[CHART-DONE]
路徑：<PNG 檔案完整路徑>
圖表類型：<使用的圖表類型>
標題：<圖表標題>
```

---

## 注意事項

- **流程圖**：若使用者要求流程圖，改用 `matplotlib.patches` 繪製方塊與箭頭，或說明 Mermaid 語法更適合並徵詢意見。
- **數據過多**：超過 12 個類別時，建議使用者篩選重點後再生成，不可強制壓縮導致不可讀。
- **單位**：y 軸標題必須標示單位，缺少時從文字推導（如「%」「件」「萬元」）。
- **matplotlib 未安裝**：若執行時出現 `ModuleNotFoundError`，先執行 `pip3 install matplotlib numpy` 再重試。
