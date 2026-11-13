# 關鍵技術模式

## 雙來源搜尋合併

WebForms 全文搜尋頁有兩個來源，必須合併才能涵蓋所有命中記錄。

```python
def _extract_current_page(page: Page) -> list[tuple[dict, object]]:
    results: list[tuple[dict, object]] = []
    seen_ids: set[str] = set()

    # ── 來源一：GridView（標題欄位命中，含結構化申請者/日期） ──
    grid = page.locator(f"#{config.RESULT_GRID_ID}")
    for tr in grid.locator("tr.GridItemS").all():
        link = tr.locator("a").first
        try:
            link_text = link.inner_text().strip() if link.count() > 0 else ""
            href = link.get_attribute("href") or ""
            full_text = tr.inner_text()
        except Exception:
            link_text, href, full_text = "", "", ""
        parsed = _parse_row({"linkText": link_text, "href": href, "fullText": full_text})
        fid = parsed.get("表單編號", "").strip()
        if fid and fid not in seen_ids:
            seen_ids.add(fid)
            results.append((parsed, link))

    # ── 來源二：全文搜尋區塊（內文命中，GridView 不含） ──
    _FORM_LINK_RE = re.compile(r"^.+?[編單]號[:：]\S+")
    try:
        for link in page.locator("a").all():
            try:
                text = link.inner_text().strip()
            except Exception:
                continue
            if not _FORM_LINK_RE.match(text):
                continue
            parsed_check = _parse_row({"linkText": text, "href": "", "fullText": text})
            fid = parsed_check.get("表單編號", "").strip()
            if not fid or fid in seen_ids:
                continue

            # JS 走 DOM 向上找含「申請者」的最小祖先元素
            ancestor_text = ""
            try:
                ancestor_text = link.evaluate("""el => {
                    let node = el;
                    for (let i = 0; i < 5; i++) {
                        node = node.parentElement;
                        if (!node) return '';
                        const t = node.innerText || '';
                        if (t.includes('申請者')) return t;  // 依系統調整關鍵字
                    }
                    return '';
                }""")
            except Exception:
                pass

            meta = _parse_fulltext_meta(ancestor_text) if ancestor_text else {}
            parsed = _parse_row({"linkText": text, "href": "", "fullText": text})
            for k, v in meta.items():
                if v and not parsed.get(k):
                    parsed[k] = v
            seen_ids.add(fid)
            results.append((parsed, link))
    except Exception:
        pass

    return results
```

**關鍵點**：
- `_FORM_LINK_RE` 過濾只有表單標題格式的連結（含「編號:」或「單號:」）
- `link.evaluate()` 比 `link.locator("xpath=..")` 可靠，直接在瀏覽器執行 JS
- `seen_ids` 去重確保 GridView 優先，全文區塊補遺

---

## 解析全文搜尋區塊的申請者/日期

全文搜尋區塊的結構通常是：
```
[標題連結]
[body 原始資料，可能含雜訊日期]
yyyy/mm/dd hh:mm          ← 申請日期（綠色）
表單名稱：X 申請者：Y 申請者部門：Z
```

```python
def _parse_fulltext_meta(ancestor_text: str) -> dict:
    result: dict = {}
    # 申請者（停在「申請者部門」之前）
    app_m = re.search(r"申請者[：:](.+?)(?=申請者部門[：:]|$)", ancestor_text)
    if app_m:
        result["申請者"] = app_m.group(1).strip()
    dept_m = re.search(r"申請者部門[：:](.+?)(?:\n|$)", ancestor_text)
    if dept_m:
        result["申請者部門"] = dept_m.group(1).strip()
    # 申請日期：取「表單名稱」出現前的最後一個日期
    # （body 原始資料含雜訊日期，要排除）
    meta_pos = ancestor_text.find("表單名稱")
    search_range = ancestor_text[:meta_pos] if meta_pos > 0 else ancestor_text
    dates = re.findall(r"\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2}", search_range)
    if dates:
        result["申請日期"] = dates[-1]
    return result
```

---

## iframe overlay 偵測與詳細頁擷取

WebForms 詳細頁常見四種開啟方式，依序偵測：

```python
def _fetch_detail_via_locator(page: Page, link_locator) -> dict:
    detail = {}
    context = page.context
    prev_url = page.url
    frame_count_before = len(page.frames)

    try:
        link_locator.click()
    except Exception as e:
        print(f"    [詳細頁] 點擊失敗：{e}")
        return detail

    page.wait_for_timeout(1500)

    # 情境一：iframe overlay（最常見，URL 不變，frame 數增加）
    try:
        for _ in range(16):          # 最多等 8 秒
            if len(page.frames) > frame_count_before:
                break
            page.wait_for_timeout(500)

        if len(page.frames) > frame_count_before:
            for frame in page.frames:
                if frame == page.main_frame:
                    continue
                try:
                    frame.wait_for_selector("text=關閉視窗", timeout=5000)
                    break
                except Exception:
                    pass
            page.wait_for_timeout(500)
            detail = _extract_label_values(page)
            _close_overlay(page)
            return detail
    except Exception:
        pass

    # 情境二：新分頁
    try:
        new_pages = [p for p in context.pages if p != page]
        if new_pages:
            new_page = new_pages[-1]
            new_page.wait_for_load_state("domcontentloaded", timeout=10000)
            detail = _extract_label_values(new_page)
            new_page.close()
            return detail
    except Exception:
        pass

    # 情境三：同頁 URL 跳轉
    try:
        if page.url != prev_url:
            detail = _extract_label_values(page)
            page.go_back()
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            return detail
    except Exception:
        pass

    # 情境四：同頁 div overlay（無 iframe）
    try:
        page.wait_for_selector("text=關閉視窗", timeout=3000)
        detail = _extract_label_values(page)
        _close_overlay(page)
    except Exception as e:
        print(f"    [詳細頁] 無法識別開啟模式：{e}")

    return detail


def _close_overlay(page: Page) -> None:
    for frame in page.frames:
        try:
            btn = frame.locator("text=關閉視窗")
            if btn.count() > 0:
                btn.first.click()
                page.wait_for_timeout(800)
                return
        except Exception:
            continue
```

**關鍵點**：`page.frames` 同時掃主頁面與所有 iframe，這是 WebForms iframe overlay 的唯一可靠方式。

---

## 標籤→值 掃描（含必填標記清洗）

WebForms 表單常在標籤前加 `*` `★` 等必填標記，且標記有時在獨立的 `<td>` 中。

```python
_LEADING_MARKS = re.compile(r'^[\s*★！!＊※◆▶]+')

def _clean_label(text: str) -> str:
    return _LEADING_MARKS.sub('', text).rstrip("：:　 ").strip()


def _scan_texts_for_labels(texts: list[str], found: dict) -> None:
    for i, text in enumerate(texts):
        clean = _clean_label(text)

        # 模式一：標籤與值分兩格，往後最多看 3 格，跳過純標記格
        if clean in DETAIL_LABELS:
            fname = DETAIL_LABELS[clean]
            if fname not in found:
                for j in range(i + 1, min(i + 4, len(texts))):
                    val = texts[j].strip()
                    val_core = _LEADING_MARKS.sub('', val).strip()
                    if not val_core:
                        continue          # 純 * 標記格，跳過
                    if _clean_label(val) in DETAIL_LABELS:
                        break             # 遇到下一個標籤，停止
                    found[fname] = val
                    break

        # 模式二：同一格「標籤：值」（如「表單審核結果：同意」）
        for label_key, fname in DETAIL_LABELS.items():
            for sep in ("：", ":"):
                if clean.startswith(label_key + sep) or text.startswith(label_key + sep):
                    raw = text if text.startswith(label_key + sep) else clean
                    val = raw[len(label_key) + len(sep):].strip()
                    if val and fname not in found:
                        found[fname] = val
                    break
```

**陷阱**：簽核表的「簽核時間」是欄標題，不能放進 DETAIL_LABELS（下一格是「簽核狀態」會被誤取）。表格型資料必須用專門函式處理。

---

## XPath 表格解析（底價單 / 項目清單）

當資料在表格中（而非 label-value 配對），必須用 XPath `normalize-space(text())` 定位表頭，否則外層包裝表格的 `inner_text()` 會把整個巢狀表格的文字帶進來，誤判表頭存在。

```python
def _extract_base_price_items(frame) -> str:
    # XPath：直接子 td/th 的文字完全等於「項目」「數量」「金額」
    xpath = (
        "//tr["
        "  (td[normalize-space(text())='項目'] or th[normalize-space(text())='項目']) and"
        "  (td[normalize-space(text())='數量'] or th[normalize-space(text())='數量']) and"
        "  (td[normalize-space(text())='金額'] or th[normalize-space(text())='金額'])"
        "]"
    )
    try:
        header_rows = frame.locator(f"xpath={xpath}").all()
    except Exception:
        return ""

    for header_row in header_rows:
        try:
            hcells = header_row.locator("td, th").all()
            header_texts = [c.inner_text().strip() for c in hcells]

            def col(name):
                return header_texts.index(name) if name in header_texts else -1

            idx_item  = col("項目")
            idx_qty   = col("數量")
            idx_price = col("單價")
            idx_total = col("金額")

            parent_table = header_row.locator("xpath=ancestor::table[1]")
            rows = parent_table.locator("tr").all()

            # 關鍵：若表頭第一格為空或數字（行號佔位），data row 不需再加 offset
            header_has_row_col = (not header_texts[0]) or header_texts[0].isdigit()
            header_found = False
            row_entries = []

            for row in rows:
                try:
                    row_texts = [c.inner_text().strip() for c in row.locator("td, th").all()]
                except Exception:
                    continue

                if not header_found:
                    if "項目" in row_texts and "數量" in row_texts and "金額" in row_texts:
                        header_found = True
                    continue

                if header_has_row_col:
                    offset = 0
                else:
                    offset = 1 if (row_texts and row_texts[0].isdigit()) else 0

                def cell(idx, rt=row_texts, off=offset):
                    i = idx + off
                    return rt[i] if (idx >= 0 and i < len(rt)) else ""

                item = cell(idx_item)
                if not item or item.isdigit():
                    continue

                parts = [item]
                qty = cell(idx_qty); price = cell(idx_price); total = cell(idx_total)
                if qty:   parts.append(f"數量{qty}")
                if price: parts.append(f"單價{price}")
                if total: parts.append(f"金額{total}")
                row_entries.append("、".join(parts))

            if row_entries:
                return " / ".join(row_entries)
        except Exception:
            continue
    return ""
```

---

## 簽核流程表解析（核准日期）

**不要**用 `last_date` 備援（系統頁面頂端時鐘會污染）。  
**要**專門掃描簽核表，找「核准結案」列的「簽核時間」。

```python
def _extract_approval_date(frame) -> str:
    xpath = (
        "//tr["
        "  (td[normalize-space(text())='簽核時間'] or th[normalize-space(text())='簽核時間']) and"
        "  (td[normalize-space(text())='簽核狀態'] or th[normalize-space(text())='簽核狀態'])"
        "]"
    )
    try:
        header_rows = frame.locator(f"xpath={xpath}").all()
    except Exception:
        return ""

    for header_row in header_rows:
        try:
            hcells = header_row.locator("td, th").all()
            header_texts = [c.inner_text().strip() for c in hcells]
            idx_time   = header_texts.index("簽核時間")   if "簽核時間" in header_texts else -1
            idx_status = header_texts.index("簽核狀態")   if "簽核狀態" in header_texts else -1
            if idx_time < 0 or idx_status < 0:
                continue

            parent_table = header_row.locator("xpath=ancestor::table[1]")
            rows = parent_table.locator("tr").all()
            header_found = False
            last_passed = ""
            case_closed = ""

            for row in rows:
                try:
                    row_texts = [c.inner_text().strip() for c in row.locator("td, th").all()]
                except Exception:
                    continue
                if not header_found:
                    if "簽核時間" in row_texts and "簽核狀態" in row_texts:
                        header_found = True
                    continue
                if idx_time < len(row_texts) and idx_status < len(row_texts):
                    status = row_texts[idx_status]
                    time_val = row_texts[idx_time].strip()
                    if status == "核准結案" and time_val:
                        case_closed = time_val
                    elif status in ("通過", "核准") and time_val:
                        last_passed = time_val

            return case_closed or last_passed
        except Exception:
            continue
    return ""
```

---

## 表單編號解析（多種格式）

WebForms 系統的表單標題格式不統一，常見：
- `修造單編號:15M98C25 修配事項:2.5噸堆高機檢修`（含「編號:」）
- `請購單號:15M99B02 請購項目:7噸堆高機`（含「單號:」，不含「編號」）

```python
def _parse_row(row: dict) -> dict:
    link = row.get("linkText", "")
    text = row.get("fullText", "")

    # 先找「...編號:」，找不到再找「...單號:」
    type_m = re.search(r"^(.+?)編號[:：]", link) or re.search(r"^(.+?)單號[:：]", link)
    num_m  = re.search(r"編號[:：](\S+)", link)  or re.search(r"單號[:：](\S+)", link)
    # 修配/請購/申購事項（依系統擴充）
    item_m = re.search(r"(?:修配事項|請購項目|申購項目|工程項目)[:：](.+)", link)
    date_m = re.search(r"(\d{4}/\d{2}/\d{2}\s+\d{2}:\d{2})", text)
    app_m  = re.search(r"申請者[：:](.+?)(?=申請者部門|$)", text, re.MULTILINE)
    dept_m = re.search(r"申請者部門[：:](.+?)(?:\n|$)", text)

    return {
        "表單類型":   type_m.group(1).strip() if type_m else "",
        "表單編號":   num_m.group(1).strip()  if num_m  else "",
        "修配事項":   item_m.group(1).strip() if item_m else "",
        "申請日期":   date_m.group(1).strip() if date_m else "",
        "申請者":     app_m.group(1).strip()  if app_m  else "",
        "申請者部門": dept_m.group(1).strip() if dept_m else "",
        "href":       row.get("href", ""),
    }
```

---

## 去重與排序

```python
# 在 collect_records 主迴圈中：
seen_ids: set[str] = set()

form_id = row.get("表單編號", "").strip()
if not form_id:
    continue          # 跳過空表單編號（搜尋結果版面有時有空列）
if form_id in seen_ids:
    continue          # 跳過重複（同一表單可能被多種規則命中）
seen_ids.add(form_id)

# 收集完後依申請日期遞減排序
records.sort(key=lambda r: r.申請日期, reverse=True)
for i, rec in enumerate(records, 1):
    rec.index = i
```

---

## 首次偵錯：印出所有 frame 的 td 文字

當詳細頁欄位抓不到時，用這個函式印出第一次執行的 frame 結構：

```python
def _debug_print_labels(page: Page) -> None:
    if not getattr(_debug_print_labels, "_done", False):
        frames = list(page.frames)
        print(f"\n  [偵錯] 共 {len(frames)} 個 frame")
        for fi, frame in enumerate(frames):
            try:
                print(f"  [偵錯] frame[{fi}] url={frame.url[:80]}")
                for i, c in enumerate(frame.locator("td").all()[:30]):
                    try:
                        print(f"    td[{fi},{i:02d}] {c.inner_text().strip()[:60]!r}")
                    except Exception:
                        pass
            except Exception as e:
                print(f"  [偵錯] frame[{fi}] 無法讀取：{e}")
        _debug_print_labels._done = True
```

觀察輸出後，把實際標籤名稱填入 `DETAIL_LABELS`。
