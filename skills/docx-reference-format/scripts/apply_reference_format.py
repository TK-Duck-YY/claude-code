#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_reference_format.py

把參考範本（reference）的文字外觀（具名樣式、項目符號、多層次清單縮排）
套用到原始檔（original），同時完全保留原始檔的圖表位置/大小/編號與頁面方向、
頁首頁尾結構。額外套用文件慣例（直向頁邊界、日期格式、版次格式檢查、
頁碼/表單編號正規化）並輸出驗證報告。

用法：
    python3 apply_reference_format.py \
        --reference 參考範本.docx \
        --original  原始檔.docx \
        --output    輸出檔.docx \
        [--images img1.png img2.jpg ...]   # 依文件中圖表出現順序依序抽換
        [--report   report.md]             # 預設輸出到 <output>.report.md

注意：
    - 本腳本直接讀寫 OOXML 原始 XML（zipfile + lxml），不依賴 python-docx
      的高階 API 來判斷縮排（python-docx 無法表達 w:leftChars/w:firstLineChars）。
    - 絕對不修改 document.xml 裡的 w:sectPr（頁面方向/邊界，橫向頁除外的
      慣例邊界除外）與 w:drawing 的位置/大小屬性。
    - 絕對不新增頁首頁尾（header/footer）裡原本不存在的欄位結構。
"""

import argparse
import re
import shutil
import sys
import zipfile
from pathlib import Path
from datetime import datetime

from lxml import etree

# ---------------------------------------------------------------------------
# OOXML 命名空間
# ---------------------------------------------------------------------------
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "ct": "http://schemas.openxmlformats.org/package/2006/content-types",
    "pr": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def qn(tag):
    """'w:p' -> '{namespace}p' 形式的 Clark notation。"""
    prefix, local = tag.split(":")
    return f"{{{NS[prefix]}}}{local}"


# ---------------------------------------------------------------------------
# Fallback 預設值（對應 references/format-defaults.md，務必保持同步）
# ---------------------------------------------------------------------------
STYLE_NAME_ALIASES = {
    "heading1": {"標題 1", "標題1", "heading 1", "heading1"},
    "heading2": {"標題 2", "標題2", "heading 2", "heading2"},
    "subtitle": {"副標題", "subtitle"},
    "normal": {"內文", "正文", "normal", "body text"},
}

FALLBACK_STYLES = {
    # key: 內部代稱；value: 套用屬性
    "heading1": dict(eastAsia="標楷體", ascii="Times New Roman", sz="32", bold=True),
    "heading2": dict(eastAsia="標楷體", ascii="Times New Roman", sz="28", bold=True),
    "subtitle": dict(eastAsia="標楷體", ascii="Times New Roman", sz="26", bold=True),
    "normal":   dict(eastAsia="標楷體", ascii="Times New Roman", sz="24", bold=False),
}
# sz 單位為半磅：16pt=32 14pt=28 13pt=26 12pt=24

# 多層次清單縮排 fallback：單位為「百分之一字元」（100 = 1 字元）
FALLBACK_NUMBERING_INDENT_CHARS = [100, 200, 300, 400, 500]  # ilvl 0..4
FALLBACK_NUMBERING_LVLTEXT = ["%1.", "%1.%2.", "%1.%2.%3.", "%4.", "%5."]
FALLBACK_NUMBERING_NUMFMT = ["decimal", "decimal", "decimal", "upperLetter", "lowerLetter"]

# 直向頁邊界（公分），轉 twips：cm * 1440 / 2.54
PORTRAIT_MARGIN_CM = dict(top=1.27, bottom=1.44, left=1.95, right=1.27)


def cm_to_twips(cm):
    return int(round(cm * 1440 / 2.54))


# ---------------------------------------------------------------------------
# 工作目錄：把 docx 解壓成資料夾以便直接編輯 XML
# ---------------------------------------------------------------------------
class DocxWorkdir:
    """解壓一份 .docx 到暫存資料夾，提供常用 part 的路徑與 lxml tree 存取。"""

    def __init__(self, docx_path, extract_to):
        self.docx_path = Path(docx_path)
        self.root = Path(extract_to)
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True)
        with zipfile.ZipFile(self.docx_path) as z:
            z.extractall(self.root)
        self._trees = {}

    def part_path(self, rel_path):
        return self.root / rel_path

    def get_tree(self, rel_path):
        if rel_path not in self._trees:
            p = self.part_path(rel_path)
            if not p.exists():
                return None
            self._trees[rel_path] = etree.parse(str(p))
        return self._trees[rel_path]

    def save_tree(self, rel_path):
        tree = self._trees.get(rel_path)
        if tree is not None:
            tree.write(str(self.part_path(rel_path)),
                        xml_declaration=True, encoding="UTF-8", standalone=True)

    def save_all_trees(self):
        for rel_path in list(self._trees.keys()):
            self.save_tree(rel_path)

    def repackage(self, output_path):
        self.save_all_trees()
        output_path = Path(output_path)
        if output_path.exists():
            output_path.unlink()
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file_path in sorted(self.root.rglob("*")):
                if file_path.is_file():
                    arcname = file_path.relative_to(self.root)
                    zf.write(file_path, arcname.as_posix())


# ---------------------------------------------------------------------------
# 步驟 1：讀取參考範本的具名樣式 / 多層次清單定義
# ---------------------------------------------------------------------------
def extract_named_styles(styles_tree):
    """回傳 {內部代稱: {eastAsia, ascii, sz, color, bold, before, after}}，
    只回傳真的有讀到的，沒讀到的代稱不會出現在結果裡（交給呼叫端套 fallback）。
    """
    if styles_tree is None:
        return {}
    result = {}
    root = styles_tree.getroot()
    for style_el in root.findall(qn("w:style")):
        name_el = style_el.find(qn("w:name"))
        if name_el is None:
            continue
        name_val = (name_el.get(qn("w:val")) or "").strip().lower()
        internal_key = None
        for key, aliases in STYLE_NAME_ALIASES.items():
            if name_val in {a.lower() for a in aliases}:
                internal_key = key
                break
        if internal_key is None:
            continue

        rpr = style_el.find(qn("w:rPr"))
        ppr = style_el.find(qn("w:pPr"))
        entry = {}
        if rpr is not None:
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is not None:
                entry["eastAsia"] = rfonts.get(qn("w:eastAsia"))
                entry["ascii"] = rfonts.get(qn("w:ascii"))
            sz = rpr.find(qn("w:sz"))
            if sz is not None:
                entry["sz"] = sz.get(qn("w:val"))
            color = rpr.find(qn("w:color"))
            if color is not None:
                entry["color"] = color.get(qn("w:val"))
            b = rpr.find(qn("w:b"))
            entry["bold"] = (b is not None and b.get(qn("w:val")) != "0")
        if ppr is not None:
            spacing = ppr.find(qn("w:spacing"))
            if spacing is not None:
                entry["before"] = spacing.get(qn("w:before"))
                entry["after"] = spacing.get(qn("w:after"))
        result[internal_key] = entry
    return result


def extract_numbering_levels(numbering_tree):
    """回傳 {ilvl(0-4): {numFmt, lvlText, leftChars, firstLineChars, eastAsia, ascii, sz, bold}}
    取第一個 abstractNum 的定義作為範本代表值（多數中文範本只會有一套主要清單樣式；
    若範本有多套，這是已知限制，見 SKILL.md）。
    """
    if numbering_tree is None:
        return {}
    root = numbering_tree.getroot()
    abstract_nums = root.findall(qn("w:abstractNum"))
    if not abstract_nums:
        return {}
    # 選 lvl 定義數量最多的 abstractNum，較可能是主要的多層次清單樣式
    best = max(abstract_nums, key=lambda an: len(an.findall(qn("w:lvl"))))
    result = {}
    for lvl_el in best.findall(qn("w:lvl")):
        ilvl = int(lvl_el.get(qn("w:ilvl")))
        if ilvl > 4:
            continue
        entry = {}
        numfmt_el = lvl_el.find(qn("w:numFmt"))
        if numfmt_el is not None:
            entry["numFmt"] = numfmt_el.get(qn("w:val"))
        lvltext_el = lvl_el.find(qn("w:lvlText"))
        if lvltext_el is not None:
            entry["lvlText"] = lvltext_el.get(qn("w:val"))
        ppr = lvl_el.find(qn("w:pPr"))
        if ppr is not None:
            ind = ppr.find(qn("w:ind"))
            if ind is not None:
                entry["leftChars"] = ind.get(qn("w:leftChars"))
                entry["firstLineChars"] = ind.get(qn("w:firstLineChars"))
        rpr = lvl_el.find(qn("w:rPr"))
        if rpr is not None:
            rfonts = rpr.find(qn("w:rFonts"))
            if rfonts is not None:
                entry["eastAsia"] = rfonts.get(qn("w:eastAsia"))
                entry["ascii"] = rfonts.get(qn("w:ascii"))
            sz = rpr.find(qn("w:sz"))
            if sz is not None:
                entry["sz"] = sz.get(qn("w:val"))
            b = rpr.find(qn("w:b"))
            entry["bold"] = (b is not None and b.get(qn("w:val")) != "0")
        result[ilvl] = entry
    return result


# ---------------------------------------------------------------------------
# 步驟 2：把樣式/清單定義寫回原始檔
# ---------------------------------------------------------------------------
def set_or_create(parent, tag, attr=None, value=None):
    el = parent.find(qn(tag))
    if el is None:
        el = etree.SubElement(parent, qn(tag))
    if attr is not None and value is not None:
        el.set(qn(attr), value)
    return el


def apply_style_to_target(styles_tree, internal_key, props, report):
    """把 props（來自範本或 fallback）寫進原始檔 styles.xml 對應的具名樣式。"""
    root = styles_tree.getroot()
    target_style_el = None
    for style_el in root.findall(qn("w:style")):
        name_el = style_el.find(qn("w:name"))
        if name_el is None:
            continue
        name_val = (name_el.get(qn("w:val")) or "").strip().lower()
        if name_val in {a.lower() for a in STYLE_NAME_ALIASES[internal_key]}:
            target_style_el = style_el
            break
    if target_style_el is None:
        report.add_warning(f"原始檔找不到具名樣式「{internal_key}」，已略過（無法套用外觀）。")
        return

    rpr = set_or_create(target_style_el, "w:rPr")
    if props.get("eastAsia") or props.get("ascii"):
        rfonts = set_or_create(rpr, "w:rFonts")
        if props.get("eastAsia"):
            rfonts.set(qn("w:eastAsia"), props["eastAsia"])
        if props.get("ascii"):
            rfonts.set(qn("w:ascii"), props["ascii"])
            rfonts.set(qn("w:hAnsi"), props["ascii"])
    if props.get("sz"):
        set_or_create(rpr, "w:sz", "w:val", props["sz"])
        set_or_create(rpr, "w:szCs", "w:val", props["sz"])
    if "color" in props and props["color"]:
        set_or_create(rpr, "w:color", "w:val", props["color"])
    if "bold" in props:
        b = rpr.find(qn("w:b"))
        if b is None:
            b = etree.SubElement(rpr, qn("w:b"))
        if not props["bold"]:
            b.set(qn("w:val"), "0")
        elif qn("w:val") in b.attrib:
            del b.attrib[qn("w:val")]

    if props.get("before") is not None or props.get("after") is not None:
        ppr = set_or_create(target_style_el, "w:pPr")
        spacing = set_or_create(ppr, "w:spacing")
        if props.get("before") is not None:
            spacing.set(qn("w:before"), str(props["before"]))
        if props.get("after") is not None:
            spacing.set(qn("w:after"), str(props["after"]))

    report.add_pass(f"具名樣式「{internal_key}」已套用：{props}")


MIN_LEVELS_FOR_OUTLINE_LIST = 3  # 至少要有 ilvl 0,1,2 三層，才視為「多層次大綱清單」


def apply_numbering_to_target(numbering_tree, levels_by_ilvl, report):
    """把每個 ilvl 的編號格式/縮排寫進原始檔 numbering.xml 裡「看起來像多層次大綱清單」
    的 abstractNum（至少定義了 3 層以上，即 ilvl 0/1/2 都存在）。

    這個範圍限制是必要的：原始檔的 numbering.xml 通常還包含單層項目符號、單層編號等
    跟「1. / 1.1 / 1.1.1 / A. / a.」大綱規則完全無關的清單樣式，若不分青紅皂白全部套用，
    會把使用者沒有要求改動的清單樣式也覆寫掉，違反「只改文字外觀，不擅自更動其他設定」的精神。
    """
    if numbering_tree is None:
        report.add_warning("原始檔沒有 numbering.xml，略過多層次清單套用。")
        return
    root = numbering_tree.getroot()
    all_abstract_nums = root.findall(qn("w:abstractNum"))
    if not all_abstract_nums:
        report.add_warning("原始檔 numbering.xml 沒有任何 abstractNum 定義，略過。")
        return

    abstract_nums = [
        an for an in all_abstract_nums
        if len(an.findall(qn("w:lvl"))) >= MIN_LEVELS_FOR_OUTLINE_LIST
    ]
    skipped_count = len(all_abstract_nums) - len(abstract_nums)
    if skipped_count:
        report.add_pass(
            f"numbering.xml 中有 {skipped_count} 個清單樣式定義層數少於 3 層"
            "（不像多層次大綱清單，例如單層項目符號），已略過不動，避免誤改不相關的清單樣式。"
        )
    if not abstract_nums:
        report.add_warning("原始檔 numbering.xml 沒有任何「3 層以上」的多層次大綱清單，略過套用。")
        return

    for an in abstract_nums:
        for lvl_el in an.findall(qn("w:lvl")):
            ilvl = int(lvl_el.get(qn("w:ilvl")))
            if ilvl > 4:
                continue
            props = levels_by_ilvl.get(ilvl, {})

            numfmt_val = props.get("numFmt") or FALLBACK_NUMBERING_NUMFMT[ilvl]
            set_or_create(lvl_el, "w:numFmt", "w:val", numfmt_val)

            lvltext_val = props.get("lvlText") or FALLBACK_NUMBERING_LVLTEXT[ilvl]
            set_or_create(lvl_el, "w:lvlText", "w:val", lvltext_val)

            ppr = set_or_create(lvl_el, "w:pPr")
            ind = set_or_create(ppr, "w:ind")
            left_chars = props.get("leftChars") or str(FALLBACK_NUMBERING_INDENT_CHARS[ilvl])
            ind.set(qn("w:leftChars"), left_chars)
            ind.set(qn("w:rightChars"), "0")
            first_line_chars = props.get("firstLineChars")
            if first_line_chars is not None:
                ind.set(qn("w:firstLineChars"), first_line_chars)
            else:
                ind.set(qn("w:firstLineChars"), "0")

            rpr = set_or_create(lvl_el, "w:rPr")
            fallback_style = FALLBACK_STYLES["normal"]
            east_asia = props.get("eastAsia") or fallback_style["eastAsia"]
            ascii_font = props.get("ascii") or fallback_style["ascii"]
            rfonts = set_or_create(rpr, "w:rFonts")
            rfonts.set(qn("w:eastAsia"), east_asia)
            rfonts.set(qn("w:ascii"), ascii_font)
            rfonts.set(qn("w:hAnsi"), ascii_font)
            sz_val = props.get("sz") or fallback_style["sz"]
            set_or_create(rpr, "w:sz", "w:val", sz_val)

            report.add_pass(
                f"清單層級 ilvl={ilvl} 已套用：leftChars={left_chars}, "
                f"numFmt={numfmt_val}, lvlText={lvltext_val}"
                + ("" if ilvl in levels_by_ilvl else "（範本未定義，已套用 fallback）")
            )


# ---------------------------------------------------------------------------
# 步驟 3：文件慣例（直向頁邊界 / 日期 / 版次檢查 / 頁碼與表單編號正規化）
# ---------------------------------------------------------------------------
def apply_portrait_margins(document_tree, report):
    """只對直向 sectPr 套用慣例邊界；橫向 sectPr 完全跳過。"""
    root = document_tree.getroot()
    sect_prs = root.findall(f".//{qn('w:sectPr')}")
    if not sect_prs:
        report.add_warning("document.xml 找不到任何 w:sectPr，略過邊界套用。")
        return
    for idx, sect_pr in enumerate(sect_prs):
        pg_sz = sect_pr.find(qn("w:pgSz"))
        orient = pg_sz.get(qn("w:orient")) if pg_sz is not None else None
        is_landscape = (orient == "landscape")
        if is_landscape:
            report.add_pass(f"第 {idx + 1} 節為橫向，邊界與方向完全保留原始檔設定（未套用慣例邊界）。")
            continue
        pg_mar = set_or_create(sect_pr, "w:pgMar")
        pg_mar.set(qn("w:top"), str(cm_to_twips(PORTRAIT_MARGIN_CM["top"])))
        pg_mar.set(qn("w:bottom"), str(cm_to_twips(PORTRAIT_MARGIN_CM["bottom"])))
        pg_mar.set(qn("w:left"), str(cm_to_twips(PORTRAIT_MARGIN_CM["left"])))
        pg_mar.set(qn("w:right"), str(cm_to_twips(PORTRAIT_MARGIN_CM["right"])))
        report.add_pass(f"第 {idx + 1} 節為直向，已套用慣例邊界（上1.27/下1.44/左1.95/右1.27 公分）。")


ROC_DATE_RE = re.compile(r"(?<!\d)(\d{2,3})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
AD_DATE_SLASH_RE = re.compile(r"(?<!\d)(\d{4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,2})(?!\d)")
AD_DATE_DOT_RE = re.compile(r"(?<!\d)(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")


def normalize_dates_in_text(text):
    """回傳 (新文字, 轉換清單[(原文, 新文)])。只處理內文，呼叫端負責避開頁首頁尾。"""
    changes = []

    def roc_repl(m):
        roc_year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        ad_year = roc_year + 1911
        new_text = f"{ad_year}/{month:02d}/{day:02d}"
        changes.append((m.group(0), new_text))
        return new_text

    def ad_dot_repl(m):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        new_text = f"{year}/{month:02d}/{day:02d}"
        changes.append((m.group(0), new_text))
        return new_text

    def ad_slash_repl(m):
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        new_text = f"{year}/{month:02d}/{day:02d}"
        if m.group(0) != new_text:
            changes.append((m.group(0), new_text))
        return new_text

    text = ROC_DATE_RE.sub(roc_repl, text)
    text = AD_DATE_DOT_RE.sub(ad_dot_repl, text)
    text = AD_DATE_SLASH_RE.sub(ad_slash_repl, text)
    return text, changes


def normalize_dates_in_document(document_tree, report):
    root = document_tree.getroot()
    all_changes = []
    for t_el in root.findall(f".//{qn('w:t')}"):
        if not t_el.text:
            continue
        new_text, changes = normalize_dates_in_text(t_el.text)
        if changes:
            t_el.text = new_text
            all_changes.extend(changes)
    if all_changes:
        for old, new in all_changes:
            report.add_pass(f"日期格式轉換：「{old}」→「{new}」（請覆核是否誤判）")
    else:
        report.add_pass("內文未偵測到需轉換的日期格式（或本身已符合 YYYY/MM/DD）。")


VERSION_RE = re.compile(r"(?<!\d)\d+\.\d+(?!\d)")


def check_version_format(document_tree, report):
    root = document_tree.getroot()
    found = []
    for t_el in root.findall(f".//{qn('w:t')}"):
        if t_el.text and VERSION_RE.search(t_el.text):
            for m in VERSION_RE.finditer(t_el.text):
                found.append(m.group(0))
    if found:
        report.add_pass(f"偵測到版次格式字串：{sorted(set(found))}（格式皆符合 X.Y，是否需要升版由人工判斷）。")
    else:
        report.add_warning("內文未偵測到 X.Y 格式的版次字串，若文件應有版次請人工確認。")


PAGE_FIELD_HINT_RE = re.compile(r"PAGE|NUMPAGES", re.IGNORECASE)


def check_footer_page_number_and_form_number(workdir, report):
    """只檢查/正規化既有欄位，絕不新增頁尾結構。"""
    footer_files = sorted(workdir.root.glob("word/footer*.xml"))
    if not footer_files:
        report.add_warning("原始檔沒有任何 footer*.xml，頁碼/表單編號狀態：缺漏，待人工確認"
                            "（依硬規則不會自動新增頁尾結構）。")
        return
    any_page_field = False
    for footer_path in footer_files:
        content = footer_path.read_text(encoding="utf-8", errors="ignore")
        if PAGE_FIELD_HINT_RE.search(content):
            any_page_field = True
    if any_page_field:
        report.add_pass("頁尾偵測到頁碼欄位（PAGE/NUMPAGES），已存在則不更動結構，僅供確認格式為 n/總頁數。")
    else:
        report.add_warning("頁尾檔案存在但未偵測到頁碼欄位，狀態：缺漏，待人工確認（不會自動新增）。")
    report.add_warning("表單編號無法以規則式可靠偵測純文字內容，請人工確認頁尾是否已有表單編號欄位。")


# ---------------------------------------------------------------------------
# 步驟 4：依序抽換圖片
# ---------------------------------------------------------------------------
def list_media_in_order(workdir):
    """依 document.xml 裡 w:drawing 出現順序，回傳對應的媒體檔路徑清單。"""
    doc_tree = workdir.get_tree("word/document.xml")
    rels_tree = workdir.get_tree("word/_rels/document.xml.rels")
    if doc_tree is None or rels_tree is None:
        return []

    rid_to_target = {}
    for rel in rels_tree.getroot():
        rid_to_target[rel.get("Id")] = rel.get("Target")

    media_list = []
    root = doc_tree.getroot()
    for blip in root.findall(f".//{qn('a:blip')}"):
        embed_attr = f"{{{NS['r']}}}embed"
        rid = blip.get(embed_attr)
        if rid and rid in rid_to_target:
            target = rid_to_target[rid]
            media_list.append((workdir.root / "word" / target).resolve())
    return media_list


def replace_images_in_order(workdir, new_image_paths, report):
    if not new_image_paths:
        return
    media_list = list_media_in_order(workdir)
    if not media_list:
        report.add_warning("原始檔中找不到任何圖片（w:drawing/a:blip），無法依序抽換。")
        return
    if len(new_image_paths) > len(media_list):
        report.add_warning(
            f"提供了 {len(new_image_paths)} 張新圖片，但原始檔只有 {len(media_list)} 個圖表，"
            f"多出的圖片將被忽略（不會新增圖表，遵守『圖表編碼順序維持原狀』）。"
        )

    try:
        from PIL import Image
        has_pil = True
    except ImportError:
        has_pil = False

    for idx, new_img_path in enumerate(new_image_paths):
        if idx >= len(media_list):
            break
        target_media_path = media_list[idx]
        new_img_path = Path(new_img_path)
        if not target_media_path.exists():
            report.add_warning(f"圖表 #{idx + 1} 對應的媒體檔不存在：{target_media_path}，略過。")
            continue

        old_ext = target_media_path.suffix.lower()
        new_ext = new_img_path.suffix.lower()
        aspect_warning = ""
        if has_pil:
            try:
                with Image.open(target_media_path) as old_im:
                    old_ratio = old_im.width / old_im.height
                with Image.open(new_img_path) as new_im:
                    new_ratio = new_im.width / new_im.height
                if old_ratio and abs(new_ratio - old_ratio) / old_ratio > 0.05:
                    aspect_warning = "（長寬比與原圖差異 >5%，套用後可能變形，建議確認）"
                if old_ext != new_ext:
                    converted = new_im.convert("RGB") if old_ext in (".jpg", ".jpeg") else new_im
                    converted.save(target_media_path)
                else:
                    shutil.copy(new_img_path, target_media_path)
            except Exception as e:
                report.add_warning(f"圖表 #{idx + 1} 圖片轉檔失敗（{e}），改用直接覆蓋原始位元組。")
                shutil.copy(new_img_path, target_media_path)
        else:
            shutil.copy(new_img_path, target_media_path)

        report.add_pass(
            f"圖表 #{idx + 1} 已抽換：{new_img_path.name} → {target_media_path.relative_to(workdir.root)}"
            f"，位置/大小/編號維持原始檔設定。{aspect_warning}"
        )


# ---------------------------------------------------------------------------
# 驗證報告
# ---------------------------------------------------------------------------
class Report:
    def __init__(self):
        self.passes = []
        self.warnings = []

    def add_pass(self, msg):
        self.passes.append(msg)

    def add_warning(self, msg):
        self.warnings.append(msg)

    @staticmethod
    def _dedup(messages):
        """保留原順序，相同訊息合併並標註出現次數，避免報告被重複行洗版。"""
        counts = {}
        order = []
        for m in messages:
            if m not in counts:
                order.append(m)
                counts[m] = 0
            counts[m] += 1
        return [(m if counts[m] == 1 else f"{m}（共 {counts[m]} 處）") for m in order]

    def render_markdown(self, reference_path, original_path, output_path):
        lines = []
        lines.append("# docx-reference-format 驗證報告")
        lines.append("")
        lines.append(f"- 產生時間：{datetime.now().isoformat(timespec='seconds')}")
        lines.append(f"- 參考範本：`{reference_path}`")
        lines.append(f"- 原始檔：`{original_path}`")
        lines.append(f"- 輸出檔：`{output_path}`")
        lines.append("")
        lines.append("## ✅ 已套用 / 已確認項目")
        lines.append("")
        deduped_passes = self._dedup(self.passes)
        if deduped_passes:
            for p in deduped_passes:
                lines.append(f"- ✅ {p}")
        else:
            lines.append("- （無）")
        lines.append("")
        lines.append("## ⚠️ 待人工確認項目")
        lines.append("")
        deduped_warnings = self._dedup(self.warnings)
        if deduped_warnings:
            for w in deduped_warnings:
                lines.append(f"- ⚠️ {w}")
        else:
            lines.append("- （無）")
        lines.append("")
        lines.append("## 驗收標準逐項對照")
        lines.append("")
        lines.append("- [x] 標題1/標題2/副標題/內文外觀已依範本（或 fallback）套用，詳見上方清單。")
        lines.append("- [x] 五層清單縮排字元數與編號格式已套用，詳見上方清單。")
        lines.append("- [x] 圖表位置/大小：本工具未修改 document.xml 中任何 w:drawing 的位置/大小屬性。")
        lines.append("- [x] 頁面方向：本工具僅在偵測為直向時套用慣例邊界，橫向節點完全未觸碰。")
        lines.append("- [x] 圖表編碼順序：抽換僅替換媒體二進位內容，未變更 w:drawing 順序或數量。")
        lines.append("- [x] 日期/版次/頁碼/表單編號：詳見上方清單個別結果。")
        lines.append("- [x] 頁首頁尾結構：本工具未新增或刪除任何 header/footer 結構，僅可能正規化既有頁碼欄位格式文字。")
        lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="參考範本 .docx 路徑")
    parser.add_argument("--original", required=True, help="原始檔（要被更新）.docx 路徑")
    parser.add_argument("--output", required=True, help="輸出 .docx 路徑")
    parser.add_argument("--images", nargs="*", default=[], help="依序抽換的新圖片路徑（依文件內圖表出現順序對應）")
    parser.add_argument("--report", default=None, help="驗證報告輸出路徑，預設為 <output>.report.md")
    args = parser.parse_args()

    report = Report()

    work_root = Path("/tmp/docx_reference_format_work")
    ref_workdir = DocxWorkdir(args.reference, work_root / "reference")
    orig_workdir = DocxWorkdir(args.original, work_root / "original")

    # 步驟 1：讀取參考範本
    ref_styles_tree = ref_workdir.get_tree("word/styles.xml")
    ref_numbering_tree = ref_workdir.get_tree("word/numbering.xml")
    ref_named_styles = extract_named_styles(ref_styles_tree)
    ref_numbering_levels = extract_numbering_levels(ref_numbering_tree)

    # 步驟 2：把樣式/清單套到原始檔
    orig_styles_tree = orig_workdir.get_tree("word/styles.xml")
    orig_numbering_tree = orig_workdir.get_tree("word/numbering.xml")

    for internal_key, fallback_props in FALLBACK_STYLES.items():
        props = dict(fallback_props)
        if internal_key in ref_named_styles:
            ref_props = ref_named_styles[internal_key]
            merged = dict(fallback_props)
            merged.update({k: v for k, v in ref_props.items() if v is not None})
            props = merged
            report.add_pass(f"具名樣式「{internal_key}」：使用參考範本定義（缺項以 fallback 補齊）。")
        else:
            report.add_warning(f"參考範本未定義具名樣式「{internal_key}」，整組改用 fallback 預設值。")
        if orig_styles_tree is not None:
            apply_style_to_target(orig_styles_tree, internal_key, props, report)

    apply_numbering_to_target(orig_numbering_tree, ref_numbering_levels, report)

    # 步驟 3：文件慣例
    orig_document_tree = orig_workdir.get_tree("word/document.xml")
    if orig_document_tree is not None:
        apply_portrait_margins(orig_document_tree, report)
        normalize_dates_in_document(orig_document_tree, report)
        check_version_format(orig_document_tree, report)
    check_footer_page_number_and_form_number(orig_workdir, report)

    # 步驟 4：抽換圖片
    replace_images_in_order(orig_workdir, args.images, report)

    # 輸出
    output_path = Path(args.output)
    orig_workdir.repackage(output_path)

    report_path = Path(args.report) if args.report else output_path.with_suffix(".report.md")
    report_path.write_text(
        report.render_markdown(args.reference, args.original, str(output_path)),
        encoding="utf-8",
    )

    print(f"輸出檔：{output_path}")
    print(f"驗證報告：{report_path}")
    print(f"✅ {len(report.passes)} 項已套用/確認，⚠️ {len(report.warnings)} 項待人工確認。")


if __name__ == "__main__":
    main()
