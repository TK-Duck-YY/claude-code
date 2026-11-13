#!/usr/bin/env python3
"""
fix_anchor_images.py
修正 Word (.docx) 浮動錨點圖片（wp:anchor）的版面

功能：
  1. 修正直向大圖尺寸（統一高度）
  2. 修正所有大圖位置（posH / posV）
  3. 標準化每張直向大圖後的空段落數
  4. （選用）清除 H3/H4 的 sectPr → 轉為不可見的 pageBreakBefore

用法：
  python fix_anchor_images.py <input.docx> [output.docx] [選項]

  python fix_anchor_images.py report.docx report_fixed.docx
  python fix_anchor_images.py report.docx report_fixed.docx --fix-sect
  python fix_anchor_images.py report.docx report_fixed.docx --start-body 195 --fix-sect
"""

import sys
import argparse
import shutil
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from lxml import etree

# ── 命名空間 ────────────────────────────────────────────────
NS_W  = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
NS_WP = 'http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing'
NS_A  = 'http://schemas.openxmlformats.org/drawingml/2006/main'

EMU_PER_CM = 360_000          # 1 cm = 360,000 EMU

def emu(cm: float) -> int:
    return int(round(cm * EMU_PER_CM))


# ── 段落工具 ────────────────────────────────────────────────

def get_style(p) -> str:
    pPr = p.find(f'{{{NS_W}}}pPr')
    if pPr is None:
        return ''
    ps = pPr.find(f'{{{NS_W}}}pStyle')
    return ps.get(qn('w:val'), '') if ps is not None else ''


def get_text(p) -> str:
    return ''.join(t.text or '' for t in p.findall(f'.//{{{NS_W}}}t'))


def is_empty_para(p) -> bool:
    if etree.QName(p).localname != 'p':
        return False
    if get_text(p).strip():
        return False
    if p.findall(f'.//{{{NS_WP}}}anchor'):
        return False
    return True


def has_sect(p) -> bool:
    pPr = p.find(f'{{{NS_W}}}pPr')
    return pPr is not None and pPr.find(f'{{{NS_W}}}sectPr') is not None


def remove_sect(p):
    pPr = p.find(f'{{{NS_W}}}pPr')
    if pPr is None:
        return
    sect = pPr.find(f'{{{NS_W}}}sectPr')
    if sect is not None:
        pPr.remove(sect)


def add_page_break_before(p):
    """在段落 pPr 加 w:pageBreakBefore（不可見，無分節標記）"""
    pPr = p.find(f'{{{NS_W}}}pPr')
    if pPr is None:
        pPr = OxmlElement('w:pPr')
        p.insert(0, pPr)
    if pPr.find(f'{{{NS_W}}}pageBreakBefore') is None:
        pb = OxmlElement('w:pageBreakBefore')
        pPr.append(pb)


def get_anchors(p):
    return p.findall(f'.//{{{NS_WP}}}anchor')


# ── 圖片工具 ────────────────────────────────────────────────

def get_dims(anchor):
    """回傳 (cx_emu, cy_emu) 或 (0, 0)"""
    ext = anchor.find(f'{{{NS_WP}}}extent')
    if ext is None:
        return 0, 0
    return int(ext.get('cx', 0)), int(ext.get('cy', 0))


def set_size(anchor, cx: int, cy: int):
    """同步更新 wp:extent 和 a:xfrm/a:ext"""
    ext = anchor.find(f'{{{NS_WP}}}extent')
    if ext is not None:
        ext.set('cx', str(cx))
        ext.set('cy', str(cy))
    for xext in anchor.findall(f'.//{{{NS_A}}}ext'):
        xext.set('cx', str(cx))
        xext.set('cy', str(cy))


def get_posV_emu(anchor):
    posV = anchor.find(f'{{{NS_WP}}}positionV')
    if posV is None:
        return None
    off = posV.find(f'{{{NS_WP}}}posOffset')
    return int(off.text) if off is not None and off.text else None


def get_posH_info(anchor):
    """回傳 (type, value)：
    ('align', 'center') 代表 relativeFrom=page, align=center
    ('offset', int_emu) 代表 relativeFrom=column, posOffset=N
    (None, None) 代表無法讀取
    """
    posH = anchor.find(f'{{{NS_WP}}}positionH')
    if posH is None:
        return None, None
    align = posH.find(f'{{{NS_WP}}}align')
    if align is not None:
        return 'align', align.text
    off = posH.find(f'{{{NS_WP}}}posOffset')
    return ('offset', int(off.text)) if off is not None and off.text else (None, None)


def set_posH_column(anchor, offset_emu: int):
    """posH = relativeFrom=column, posOffset=offset_emu"""
    posH = anchor.find(f'{{{NS_WP}}}positionH')
    if posH is None:
        return
    for child in list(posH):
        posH.remove(child)
    posH.set('relativeFrom', 'column')
    off = OxmlElement('wp:posOffset')
    off.text = str(offset_emu)
    posH.append(off)


def set_posH_page_center(anchor):
    """posH = relativeFrom=page, align=center"""
    posH = anchor.find(f'{{{NS_WP}}}positionH')
    if posH is None:
        return
    for child in list(posH):
        posH.remove(child)
    posH.set('relativeFrom', 'page')
    align = OxmlElement('wp:align')
    align.text = 'center'
    posH.append(align)


def set_posV_paragraph(anchor, offset_emu: int):
    """posV = relativeFrom=paragraph, posOffset=offset_emu"""
    posV = anchor.find(f'{{{NS_WP}}}positionV')
    if posV is None:
        return
    for child in list(posV):
        posV.remove(child)
    posV.set('relativeFrom', 'paragraph')
    off = OxmlElement('wp:posOffset')
    off.text = str(offset_emu)
    posV.append(off)


# ── 主修正函式 ──────────────────────────────────────────────

def step_fix_images(body, cfg, stats):
    """修正所有直向/橫向大圖的尺寸與位置"""
    tgt_h  = emu(cfg.portrait_height)
    p_posv = emu(cfg.portrait_posv)
    p_posh = emu(cfg.portrait_posh)
    l_posv = emu(cfg.landscape_posv)
    p_min  = emu(cfg.portrait_min)
    l_min  = emu(cfg.landscape_min)
    tol    = emu(0.1)   # 0.1 cm 容差

    for i, p in enumerate(body):
        if i < cfg.start_body:
            continue
        if etree.QName(p).localname != 'p':
            continue
        for anchor in get_anchors(p):
            cx, cy = get_dims(anchor)
            if cx == 0 and cy == 0:
                continue

            is_portrait  = cy > cx and cy >= p_min
            is_landscape = cx >= cy and cx >= l_min and cy >= l_min

            if is_portrait:
                # ─ 尺寸：統一高度，等比縮放寬度
                if abs(cy - tgt_h) > tol:
                    new_cx = int(cx * tgt_h / cy)
                    set_size(anchor, new_cx, tgt_h)
                    stats['portrait_resized'] += 1
                # ─ posH：只在偏差超過容差（或已為 align 模式）時才設定
                ph_type, ph_val = get_posH_info(anchor)
                if ph_type == 'align' or ph_val is None or abs(ph_val - p_posh) > tol:
                    set_posH_column(anchor, p_posh)
                    stats['portrait_repositioned'] += 1
                # ─ posV
                posv = get_posV_emu(anchor)
                if posv is None or abs(posv - p_posv) > tol:
                    set_posV_paragraph(anchor, p_posv)
                    stats['portrait_repositioned'] += 1

            elif is_landscape:
                # ─ posH = 頁面置中（已是 center 則不動）
                ph_type, ph_val = get_posH_info(anchor)
                if ph_type != 'align' or ph_val != 'center':
                    set_posH_page_center(anchor)
                    stats['landscape_repositioned'] += 1
                # ─ posV
                posv = get_posV_emu(anchor)
                if posv is None or abs(posv - l_posv) > tol:
                    set_posV_paragraph(anchor, l_posv)
                    stats['landscape_repositioned'] += 1


def step_fix_empty_paras(body, cfg, stats):
    """
    每個 H4 直向大圖段落後，標準化空段落數為 cfg.empty_paras。
    若後方空段落含顯式換頁符（w:br type=page），跳過不動。
    """
    p_min   = emu(cfg.portrait_min)
    target  = cfg.empty_paras

    i = cfg.start_body
    while i < len(body):
        p = body[i]
        if etree.QName(p).localname != 'p' or get_style(p) != '4':
            i += 1
            continue

        # 確認有直向大圖
        has_portrait = any(
            get_dims(a)[1] > get_dims(a)[0] and get_dims(a)[1] >= p_min
            for a in get_anchors(p)
        )
        if not has_portrait:
            i += 1
            continue

        # 收集後方空段落
        j = i + 1
        empty_idx = []
        while j < len(body):
            pj = body[j]
            if etree.QName(pj).localname != 'p':
                break
            sj = get_style(pj)
            if sj in ('1', '2', '3', '4') or not is_empty_para(pj):
                break
            # 若有顯式換頁符，停止（已有換頁，不需要空段落）
            if pj.findall(f'.//{{{NS_W}}}br[@{{{NS_W}}}type="page"]'):
                break
            empty_idx.append(j)
            j += 1

        current = len(empty_idx)
        if current < target:
            ref = body[empty_idx[-1]] if empty_idx else p
            for _ in range(target - current):
                new_p = OxmlElement('w:p')
                ref.addnext(new_p)
                stats['empty_added'] += 1
        elif current > target:
            for k in reversed(empty_idx[target:]):
                ep = body[k]
                ep.getparent().remove(ep)
                stats['empty_removed'] += 1

        i = j


def step_fix_sect(body, cfg, stats):
    """
    將 H4 圖片段落的 sectPr 替換為 pageBreakBefore（不可見）：

    1. 移除空段落上的 sectPr（避免空白頁）
    2. 找出所有「H4 + 圖片 + sectPr」序列：
       - 移除 sectPr
       - 移除緊前 H3 的 sectPr（讓 H3 和首圖共頁）
       - 序列第 2 張起加 pageBreakBefore
       - 序列後的第一個有內容段落加 pageBreakBefore（銜接下一章）
    """
    # 1. 移除空段落 sectPr
    for p in body:
        if etree.QName(p).localname == 'p' and is_empty_para(p) and has_sect(p):
            remove_sect(p)
            stats['empty_sect_removed'] += 1

    # 重新建立 body 列表（可能因空段落刪除而變動）
    # 注意：這裡 body 是 list snapshot，不是動態的；直接用 index 即可
    # 找所有 H4 + 圖 + sectPr
    h4s = [i for i, p in enumerate(body)
           if etree.QName(p).localname == 'p'
           and get_style(p) == '4'
           and get_anchors(p)
           and has_sect(p)]

    if not h4s:
        return

    # 移除這些 H4 的 sectPr
    for idx in h4s:
        remove_sect(body[idx])
        stats['h4_sect_removed'] += 1

    # 分組為連續序列（兩 H4 之間若只有空段落，且無 H3，視為同序列）
    groups = []
    i = 0
    while i < len(h4s):
        seq = [h4s[i]]
        while i + 1 < len(h4s):
            cur, nxt = h4s[i], h4s[i + 1]
            gap = [body[k] for k in range(cur + 1, nxt)
                   if etree.QName(body[k]).localname == 'p']
            if all(is_empty_para(gp) for gp in gap) and not any(get_style(gp) == '3' for gp in gap):
                seq.append(h4s[i + 1])
                i += 1
            else:
                break
        groups.append(seq)
        i += 1

    for seq in groups:
        first_idx = seq[0]

        # 移除緊前 H3 的 sectPr（讓 H3 與首圖共頁）
        for back in range(first_idx - 1, max(-1, first_idx - 6), -1):
            bp = body[back]
            if etree.QName(bp).localname != 'p':
                continue
            s = get_style(bp)
            if s == '3':
                if has_sect(bp):
                    remove_sect(bp)
                    stats['h3_sect_removed'] += 1
                break
            if s in ('1', '2', '4') or (not is_empty_para(bp) and not s):
                break

        # 第 2 張起加 pageBreakBefore
        for idx in seq[1:]:
            add_page_break_before(body[idx])
            stats['pbr_added'] += 1

        # 序列後第一個有實質內容的段落加 pageBreakBefore（銜接下一節）
        last_idx = seq[-1]
        for fwd in range(last_idx + 1, min(len(body), last_idx + 15)):
            fp = body[fwd]
            if etree.QName(fp).localname != 'p':
                continue
            if is_empty_para(fp):
                continue
            add_page_break_before(fp)
            stats['pbr_added'] += 1
            break


# ── CLI 入口 ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description='修正 Word (.docx) 浮動錨點圖片版面',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument('input',  help='輸入 .docx 路徑')
    parser.add_argument('output', nargs='?', help='輸出 .docx（預設：原名 + _fixed）')

    g = parser.add_argument_group('圖片幾何參數')
    g.add_argument('--portrait-height', type=float, default=22.6,  metavar='CM', help='直向大圖目標高度 [22.6]')
    g.add_argument('--portrait-posv',   type=float, default=0.500, metavar='CM', help='直向大圖 posV from paragraph [0.500]')
    g.add_argument('--portrait-posh',   type=float, default=1.241, metavar='CM', help='直向大圖 posH from column [1.241]')
    g.add_argument('--landscape-posv',  type=float, default=0.500, metavar='CM', help='橫向大圖 posV from paragraph [0.500]')
    g.add_argument('--portrait-min',    type=float, default=18.0,  metavar='CM', help='直向大圖最小高度門檻 [18.0]')
    g.add_argument('--landscape-min',   type=float, default=10.0,  metavar='CM', help='橫向大圖最小尺寸門檻 [10.0]')

    g2 = parser.add_argument_group('空段落參數')
    g2.add_argument('--empty-paras', type=int, default=4, metavar='N', help='直向大圖後空段落數 [4]')

    g3 = parser.add_argument_group('執行範圍')
    g3.add_argument('--start-body', type=int, default=0, metavar='N',
                    help='從第 N 個 body element 開始（前段已手動排好時用）[0]')

    g4 = parser.add_argument_group('模式開關')
    g4.add_argument('--fix-sect',      action='store_true', help='清除 H3/H4 的 sectPr → pageBreakBefore')
    g4.add_argument('--no-fix-images', action='store_true', help='跳過圖片幾何修正')
    g4.add_argument('--no-fix-paras',  action='store_true', help='跳過空段落標準化')

    cfg = parser.parse_args()

    in_path  = Path(cfg.input)
    out_path = Path(cfg.output) if cfg.output else in_path.with_stem(in_path.stem + '_fixed')

    if not in_path.exists():
        print(f'❌ 找不到輸入檔：{in_path}', file=sys.stderr)
        sys.exit(1)

    print(f'📄 讀取：{in_path}')
    doc  = Document(str(in_path))
    body = list(doc.element.body)

    stats = dict(
        portrait_resized=0, portrait_repositioned=0,
        landscape_repositioned=0,
        empty_added=0, empty_removed=0,
        empty_sect_removed=0, h3_sect_removed=0,
        h4_sect_removed=0, pbr_added=0,
    )

    if not cfg.no_fix_images:
        print('🖼  修正圖片尺寸與位置...')
        step_fix_images(body, cfg, stats)

    if not cfg.no_fix_paras:
        print('📝 標準化空段落數...')
        step_fix_empty_paras(body, cfg, stats)

    if cfg.fix_sect:
        print('🔧 清除 sectPr → pageBreakBefore...')
        step_fix_sect(body, cfg, stats)

    doc.save(str(out_path))
    print(f'\n✅ 輸出：{out_path}')
    print('\n📊 修正統計：')
    labels = {
        'portrait_resized':      '直向圖片重設尺寸',
        'portrait_repositioned': '直向圖片重設位置',
        'landscape_repositioned':'橫向圖片重設位置',
        'empty_added':           '新增空段落',
        'empty_removed':         '移除多餘空段落',
        'empty_sect_removed':    '移除空段落 sectPr',
        'h3_sect_removed':       '移除 H3 sectPr',
        'h4_sect_removed':       '移除 H4 sectPr',
        'pbr_added':             '加 pageBreakBefore',
    }
    any_change = False
    for key, label in labels.items():
        if stats[key]:
            print(f'  {label}：{stats[key]}')
            any_change = True
    if not any_change:
        print('  （無修改）')


if __name__ == '__main__':
    main()
