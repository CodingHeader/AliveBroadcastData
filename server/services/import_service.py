def parse_schedule_xlsx(file_content: bytes, db) -> dict:
    """解析直播排班表.xlsx，创建按天排班实例（ScheduleDay + ScheduleDayAnchor）
    同时创建 SchedulePlan + ScheduleSlot + ScheduleBinding 使数据在排班日历可见。

    6月/7月 sheet 结构（含大量合并单元格）：
      Row 6: 子表头（日期, 时间段, 主播, 时长, ...）
      Row 7+: 数据行
    按日期+主播分组，保留每个主播的所有时段（支持多段如 08:00-10:00\n12:00-14:00）
    """
    from models import ScheduleDay, ScheduleDayAnchor, SchedulePlan, ScheduleSlot, ScheduleBinding, Anchor
    import zipfile, io, xml.etree.ElementTree as ET, re
    from collections import defaultdict

    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    daily_data = defaultdict(lambda: defaultdict(list))
    total_rows = 0

    def _col_letter_to_num(col: str) -> int:
        n = 0
        for ch in col:
            n = n * 26 + (ord(ch.upper()) - ord('A') + 1)
        return n

    def _num_to_col_letter(n: int) -> str:
        s = ''
        while n > 0:
            n, r = divmod(n - 1, 26)
            s = chr(ord('A') + r) + s
        return s

    def _col_range(start_col: str, end_col: str):
        a, b = _col_letter_to_num(start_col), _col_letter_to_num(end_col)
        return [_num_to_col_letter(i) for i in range(min(a, b), max(a, b) + 1)]

    with zipfile.ZipFile(io.BytesIO(file_content)) as z:
        ss_xml = z.read('xl/sharedStrings.xml')
        ss_root = ET.fromstring(ss_xml)
        shared_strings = []
        for si in ss_root.findall('.//s:si', ns):
            texts = []
            for t in si.findall('.//s:t', ns):
                if t.text:
                    texts.append(t.text)
            shared_strings.append(''.join(texts))

        wb_xml = z.read('xl/workbook.xml')
        wb_root = ET.fromstring(wb_xml)
        ns_wb = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
                 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
        sheet_entries = []
        for sheet_elem in wb_root.findall('.//s:sheet', ns_wb):
            name = sheet_elem.get('name', '')
            r_id = sheet_elem.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', '')
            sheet_entries.append((name, r_id))

        rels_xml = z.read('xl/_rels/workbook.xml.rels')
        rels_root = ET.fromstring(rels_xml)
        rels_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
        sheet_path_map = {}
        for rel in rels_root.findall('.//r:Relationship', rels_ns):
            rid = rel.get('Id', '')
            target = rel.get('Target', '')
            sheet_path_map[rid] = target

        for sheet_name, r_id in sheet_entries:
            if sheet_name not in ('6月', '7月'):
                continue

            sheet_path = sheet_path_map.get(r_id, '')
            if not sheet_path.startswith('xl/'):
                sheet_path = 'xl/' + sheet_path
            if sheet_path not in z.namelist():
                continue

            sheet_xml = z.read(sheet_path)
            sheet_root = ET.fromstring(sheet_xml)

            # ===== 解析合并单元格，构建回填映射 =====
            # merge_fill[(col_letter, row_num)] = value
            merge_fill = {}
            try:
                merge_cells = sheet_root.find('.//s:mergeCells', ns)
                if merge_cells is not None:
                    for mc in merge_cells.findall('s:mergeCell', ns):
                        ref = mc.get('ref', '')
                        if ':' not in ref:
                            continue
                        top_left, bottom_right = ref.split(':')
                        tl_match = re.match(r'([A-Z]+)(\d+)', top_left)
                        br_match = re.match(r'([A-Z]+)(\d+)', bottom_right)
                        if not (tl_match and br_match):
                            continue
                        tl_col, tl_row = tl_match.group(1), int(tl_match.group(2))
                        br_col, br_row = br_match.group(1), int(br_match.group(2))
                        # 先在 rows_data 中查找左上角的值
                        # 先收集所有行数据到一个临时字典
                        # 因为此时还没解析，先保存合并范围，后续解析时使用
                        for rn in range(tl_row, br_row + 1):
                            for cidx in _col_range(tl_col, br_col):
                                merge_fill[(cidx, rn)] = {
                                    'src_col': tl_col, 'src_row': tl_row,
                                    'value': None,  # 解析时填充
                                }
            except Exception:
                pass

            # 读取所有行数据到 rows_data，同时回填合并单元格
            rows_data = {}
            for row_elem in sheet_root.findall('.//s:row', ns):
                row_num = int(row_elem.get('r', '0'))
                if row_num < 6:
                    continue
                cells = {}
                for c in row_elem.findall('s:c', ns):
                    col_ref = c.get('r', '')
                    col_letter = re.match(r'([A-Z]+)', col_ref).group(1) if col_ref else ''
                    cell_type = c.get('t', '')
                    value_elem = c.find('s:v', ns)
                    cell_value = ''
                    if value_elem is not None and value_elem.text:
                        if cell_type == 's' and value_elem.text.isdigit():
                            idx = int(value_elem.text)
                            if idx < len(shared_strings):
                                cell_value = shared_strings[idx]
                        else:
                            cell_value = value_elem.text
                    cells[col_letter] = cell_value
                rows_data[row_num] = cells

            # 回填合并单元格的值：将左上角的值填充到所有被合并的坐标
            for (col_letter, row_num), fill_info in merge_fill.items():
                src_cells = rows_data.get(fill_info['src_row'])
                if src_cells and fill_info['src_col'] in src_cells:
                    val = src_cells[fill_info['src_col']]
                    if val:
                        fill_info['value'] = val
                        if row_num in rows_data:
                            rows_data[row_num][col_letter] = val
                        else:
                            rows_data[row_num] = {col_letter: val}

            # 解析表头行（Row 6）
            header_cols = {}
            row6 = rows_data.get(6, {})
            for col_letter, cell_value in row6.items():
                if cell_value:
                    header_cols[col_letter] = cell_value

            col_date = col_anchor = col_time = col_teacher = None
            for col_letter, hname in header_cols.items():
                if hname == '日期': col_date = col_letter
                if hname == '时间段': col_time = col_letter
                if hname in ('主播', '直播人员'): col_anchor = col_letter
                if hname in ('招生老师', '老师', '跟进老师'): col_teacher = col_letter

            if not col_date or not col_time:
                continue

            # 用于去重：同一 sheet 中相同 (anchor, start, end) 只保留一个
            seen_slots = set()

            # 解析数据行（Row 7+）
            for row_num in sorted(rows_data.keys()):
                if row_num < 7:
                    continue
                cells = rows_data[row_num]

                date_val = cells.get(col_date, '').strip()
                if not date_val:
                    continue

                # 处理日期格式：M.D / M-D / YYYY-MM-DD
                date_norm = date_val.replace('/', '-').replace('.', '-')
                m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_norm)
                if m:
                    date_str = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                else:
                    m = re.match(r'(\d{1,2})-(\d{1,2})', date_norm)
                    if not m:
                        continue
                    month, day = int(m.group(1)), int(m.group(2))
                    year = 2026
                    if month > 7:
                        year -= 1
                    date_str = f"{year}-{month:02d}-{day:02d}"

                anchor = cells.get(col_anchor, '').strip() if col_anchor else ''
                if not anchor:
                    continue

                time_val = cells.get(col_time, '').strip() if col_time else ''
                if not time_val:
                    continue
                total_rows += 1

                # 标准化时间段分隔符
                time_clean = time_val.replace('——', '-').replace('–', '-').replace('—', '-').replace('--', '-')
                # 按换行/逗号/竖线分割多段时间
                nl = chr(10)
                segments = re.split(f'[{nl}|,]', time_clean)
                for seg in segments:
                    seg = seg.strip()
                    if not seg:
                        continue
                    if '-' in seg:
                        parts = seg.split('-')
                        if len(parts) >= 2:
                            st = parts[0].strip()
                            et = parts[-1].strip()
                            if st and et:
                                # 去重：相同日期+主播+时间段只保留一个
                                key = (date_str, anchor, st, et)
                                if key not in seen_slots:
                                    seen_slots.add(key)
                                    daily_data[date_str][anchor].append({'start': st, 'end': et})

    if not daily_data:
        return {'inserted': 0, 'skipped': 0, 'anchors': 0, 'error': '没有找到有效排班数据'}

    def _calc_h(s, e):
        try:
            sh, sm = s.split(':')
            eh, em = e.split(':')
            start_min = int(sh) * 60 + int(sm)
            end_min = int(eh) * 60 + int(em)
            if end_min <= start_min:
                end_min += 24 * 60  # 跨天
            return (end_min - start_min) / 60
        except:
            return 0

    total_inserted = 0
    total_skipped = 0
    total_updated = 0
    total_anchors = 0

    for date_str in sorted(daily_data.keys()):
        exist = db.query(ScheduleDay).filter(ScheduleDay.date == date_str).first()
        if exist:
            # 存在则更新
            exist.source = "schedule_import"
            exist.notes = json.dumps({"source": "schedule_import"}, ensure_ascii=False)
            # 重建主播安排
            db.query(ScheduleDayAnchor).filter(ScheduleDayAnchor.day_id == exist.id).delete()
            day = exist
            total_updated += 1
        else:
            day = ScheduleDay(date=date_str, source="schedule_import",
                              notes=json.dumps({'source': 'schedule_import'}, ensure_ascii=False))
            db.add(day)
            db.flush()
            total_inserted += 1

        anchors = daily_data[date_str]
        for order, (anchor_name, slots) in enumerate(sorted(anchors.items())):
            unique_slots = []
            for s in slots:
                if s not in unique_slots:
                    unique_slots.append(s)
            total_h = sum(_calc_h(s['start'], s['end']) for s in unique_slots)
            sa = ScheduleDayAnchor(
                day_id=day.id, anchor_name=anchor_name,
                time_slots=json.dumps(unique_slots, ensure_ascii=False),
                total_hours=round(total_h, 1),
                order_index=order,
            )
            db.add(sa)
            total_anchors += 1

    db.commit()

    # ===== 同步到 SchedulePlan + ScheduleBinding + ScheduleSlot（排班日历可见） =====
    # 策略：按 (时间范围, 主播数) 分组，相同模式的日期共用同一个 SchedulePlan 模板
    # 每个日期独立创建 ScheduleBinding 关联到对应模板
    from collections import OrderedDict

    # 第一遍：计算每个日期的时间范围，按模式分组
    date_patterns = OrderedDict()  # (start, end, anchor_count) -> [date_str]
    date_anchor_info = {}  # date_str -> [(anchor_name, slots)]

    for date_str in sorted(daily_data.keys()):
        existing_binding = db.query(ScheduleBinding).filter(ScheduleBinding.date == date_str).first()
        if existing_binding:
            continue

        anchors = daily_data[date_str]
        sorted_anchors = sorted(anchors.items())
        anchor_count = len(sorted_anchors)
        if anchor_count == 0:
            continue

        # 计算时间范围（处理跨天）
        all_starts = []
        all_ends = []
        for anchor_name, slots in sorted_anchors:
            for s in slots:
                sp = s['start'].split(':')
                ep = s['end'].split(':')
                sm = int(sp[0]) * 60 + int(sp[1])
                em = int(ep[0]) * 60 + int(ep[1])
                if em < sm or em <= 360:
                    em += 24 * 60
                all_starts.append(sm)
                all_ends.append(em)
        if not all_starts:
            continue
        all_starts.sort()
        all_ends.sort()
        start_time = f"{all_starts[0] // 60:02d}:{all_starts[0] % 60:02d}"
        end_time = f"{all_ends[-1] % (24 * 60) // 60:02d}:{all_ends[-1] % (24 * 60) % 60:02d}"

        pattern_key = (start_time, end_time, anchor_count)
        date_patterns.setdefault(pattern_key, []).append(date_str)
        date_anchor_info[date_str] = sorted_anchors

    if not date_patterns:
        return {
            'inserted': total_inserted, 'skipped': total_skipped,
            'anchors': total_anchors, 'total_dates': len(daily_data),
            'plan_bindings_created': 0,
        }

    # 创建所有主播记录
    anchor_name_to_id = {}
    for date_str, sorted_anchors in date_anchor_info.items():
        for anchor_name, slots in sorted_anchors:
            if anchor_name in anchor_name_to_id:
                continue
            existing = db.query(Anchor).filter(Anchor.name == anchor_name).first()
            if existing:
                anchor_name_to_id[anchor_name] = existing.id
            else:
                new_anchor = Anchor(name=anchor_name, gender="", style="")
                db.add(new_anchor)
                db.flush()
                anchor_name_to_id[anchor_name] = new_anchor.id

    # 为每个模式创建 SchedulePlan + 收集所有唯一 slot
    plan_bindings_created = 0
    plan_cache = {}  # pattern_key -> plan_id

    for pattern_key, dates in date_patterns.items():
        start_time, end_time, anchor_count = pattern_key
        # 收集该模式所有日期的唯一 slot
        seen_slots = set()
        all_slots = []  # (anchor_slot, time_slot)
        anchor_slot_map = {}  # anchor_name -> anchor_slot (1-based)
        slot_order = 0
        for date_str in dates:
            sorted_anchors = date_anchor_info[date_str]
            for anchor_name, slots in sorted_anchors:
                if anchor_name not in anchor_slot_map:
                    slot_order += 1
                    anchor_slot_map[anchor_name] = slot_order
                for s in slots:
                    ts = f"{s['start']}-{s['end']}"
                    key = (anchor_slot_map[anchor_name], ts)
                    if key not in seen_slots:
                        seen_slots.add(key)
                        all_slots.append(key)

        # 创建方案名：导入排班-{start_time}~{end_time}-{anchor_count}人
        plan_name = f"导入排班-{start_time}~{end_time}-{anchor_count}人"
        plan = SchedulePlan(
            name=plan_name,
            start_time=start_time,
            end_time=end_time,
            time_granularity=60,
            room_count=1,
            anchor_count=anchor_count,
            is_active=True,
            notes=json.dumps({"source": "schedule_import", "type": "parse_schedule_xlsx"}, ensure_ascii=False),
        )
        db.add(plan)
        db.flush()

        # 创建 ScheduleSlot
        for a_slot, ts in all_slots:
            slot = ScheduleSlot(
                plan_id=plan.id,
                time_slot=ts,
                room_index=1,
                slot_status="on_air_anchor",
                anchor_slot=a_slot,
            )
            db.add(slot)

        plan_cache[pattern_key] = plan.id

        # 为该模式下的每个日期创建 ScheduleBinding
        for date_str in dates:
            sorted_anchors = date_anchor_info[date_str]
            anchor_mapping = {}
            for anchor_name, slots in sorted_anchors:
                a_slot = anchor_slot_map.get(anchor_name)
                if a_slot and slots:
                    anchor_mapping[str(a_slot)] = str(anchor_name_to_id[anchor_name])
            if not anchor_mapping:
                continue
            binding = ScheduleBinding(
                date=date_str,
                plan_id=plan.id,
                anchor_mapping=json.dumps(anchor_mapping, ensure_ascii=False),
            )
            db.add(binding)
            plan_bindings_created += 1

    db.commit()
    return {
        'inserted': total_inserted, 'updated': total_updated, 'skipped': total_skipped,
        'anchors': total_anchors, 'total_dates': len(daily_data),
        'plan_bindings_created': plan_bindings_created,
    }#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多维数据导入服务
- 多Sheet XLSX解析（使用zipfile+XML，绕过openpyxl对WPS/腾讯文档的样式兼容bug）
- CSV解析（自动检测编码和分隔符）
- Sheet类型自动识别（按列名指纹）
- 联系方式+微信归一化去重
- 导入批次日志与跳过记录
"""

import csv
import io
import json
import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# =============================================================================
# Sheet类型注册表
# =============================================================================

SHEET_TYPE_REGISTRY = {
    "education": {
        "name_keywords": ["教育在线", "教育"],
        "header_signatures": ["报考专业", "报考层次", "目前学历", "报考学校", "意向专业"],
        "contact_col_aliases": ["电话号码", "电话", "phone", "手机号", "联系方式"],
        "wechat_col_aliases": ["微信", "weixin", "wechat"],
        "name_col_aliases": ["姓名", "name", "学生姓名", "昵称"],
        "date_col_aliases": ["时间", "分配日期", "日期", "留资时间"],
        "teacher_col_aliases": ["招生老师", "老师", "跟进老师"],
        "status_col_aliases": ["数据状态", "状态标签", "跟进状态"],
        "has_contact": True,
    },
    "douyin_ops": {
        "name_keywords": ["抖音代运营", "代运营", "抖音"],
        "header_signatures": ["联系方式", "第一次跟进", "提升形式", "咨询反馈"],
        "contact_col_aliases": ["联系方式", "电话", "phone", "手机号"],
        "wechat_col_aliases": ["微信", "weixin", "wechat"],
        "name_col_aliases": ["姓名", "name", "学生姓名"],
        "date_col_aliases": ["分配日", "留资时间", "日期", "分配月"],
        "teacher_col_aliases": ["招生老师", "老师", "跟进老师"],
        "status_col_aliases": ["数据状态", "状态标签"],
        "has_contact": True,
        "has_wechat": False,  # 抖音代运营表通常没有微信列
    },
    "moment_ad": {
        "name_keywords": ["朋友圈广告", "朋友圈"],
        "header_signatures": ["日消耗", "学生姓名", "客户简单信息", "学历层次"],
        "contact_col_aliases": ["联系方式", "电话", "phone", "手机号"],
        "wechat_col_aliases": ["微信", "weixin", "wechat"],
        "name_col_aliases": ["学生姓名", "姓名", "name"],
        "date_col_aliases": ["分配日", "分配月", "日期"],
        "teacher_col_aliases": ["招生老师", "老师", "跟进老师"],
        "status_col_aliases": ["咨询反馈"],
        "has_contact": True,
        "has_wechat": False,
    },
    "live_lead": {
        "name_keywords": ["直播数据分配", "数据分配", "直播数据"],
        "header_signatures": ["直播人员", "留资方式", "投放账户", "单元名称", "留资路径", "互动场景", "主播", "流量源"],
        "contact_col_aliases": ["联系方式", "电话", "phone", "手机号"],
        "wechat_col_aliases": ["微信", "weixin", "wechat"],
        "name_col_aliases": ["用户昵称", "昵称", "姓名", "name"],
        "date_col_aliases": ["留资日期", "留资时间", "日期", "分配日"],
        "teacher_col_aliases": ["招生老师", "老师", "跟进老师"],
        "status_col_aliases": ["数据状态", "状态标签", "客户简单信息"],
        "has_contact": True,
    },
    "schedule": {
        "name_keywords": ["排班", "排班表"],
        "header_signatures": ["营销消耗", "总线索", "直播人员", "直播时间", "总时长"],
        "contact_col_aliases": [],
        "wechat_col_aliases": [],
        "name_col_aliases": [],
        "date_col_aliases": ["日期"],
        "teacher_col_aliases": ["运营值班人员", "值班人员"],
        "status_col_aliases": [],
        "has_contact": False,  # 排班表无联系方式
        "is_operational": True,
    },
    "operational": {
        "name_keywords": ["值班", "运营值班"],
        "header_signatures": ["人员", "事宜"],
        "contact_col_aliases": [],
        "wechat_col_aliases": [],
        "name_col_aliases": [],
        "date_col_aliases": ["日期"],
        "teacher_col_aliases": [],
        "status_col_aliases": [],
        "has_contact": False,
        "is_operational": True,
    },
}

SHEET_TYPE_ORDER = ["education", "live_lead", "moment_ad", "douyin_ops", "schedule", "operational"]


# =============================================================================
# 读取引擎
# =============================================================================

class ParsedSheet:
    """解析后的Sheet数据"""
    def __init__(self, index: int, name: str, headers: List[str], rows: List[Dict[str, str]]):
        self.index = index
        self.name = name
        self.headers = headers
        self.rows = rows

    def __repr__(self):
        return f"ParsedSheet(idx={self.index}, name='{self.name}', rows={len(self.rows)}, headers={self.headers[:5]}...)"


def read_xlsx(file_content: bytes) -> List[ParsedSheet]:
    """使用zipfile+xml.etree解析xlsx，绕过openpyxl的样式兼容bug
    支持多sheet、共享字符串、内联字符串
    """
    sheets = []
    try:
        with zipfile.ZipFile(io.BytesIO(file_content)) as z:
            # 读取共享字符串表
            shared_strings = []
            if 'xl/sharedStrings.xml' in z.namelist():
                ss_xml = z.read('xl/sharedStrings.xml')
                ss_root = ET.fromstring(ss_xml)
                ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in ss_root.findall('.//s:si', ns):
                    texts = []
                    for t in si.findall('.//s:t', ns):
                        if t.text:
                            texts.append(t.text)
                    shared_strings.append(''.join(texts))

            # 读取workbook.xml获取sheet列表
            wb_xml = z.read('xl/workbook.xml')
            wb_root = ET.fromstring(wb_xml)
            ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
                  'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
            sheet_entries = []
            for sheet_elem in wb_root.findall('.//s:sheet', ns):
                name = sheet_elem.get('name', '')
                sheet_id = sheet_elem.get('sheetId', '')
                r_id = sheet_elem.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id', '')
                sheet_entries.append((int(sheet_id), name, r_id))

            # 读取关系文件获取sheet文件路径
            rels_xml = z.read('xl/_rels/workbook.xml.rels')
            rels_root = ET.fromstring(rels_xml)
            rels_ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
            sheet_path_map = {}
            for rel in rels_root.findall('.//r:Relationship', rels_ns):
                rid = rel.get('Id', '')
                target = rel.get('Target', '')
                sheet_path_map[rid] = target

            for sheet_id, sheet_name, r_id in sheet_entries:
                sheet_path = sheet_path_map.get(r_id, f'worksheets/sheet{sheet_id}.xml')
                if not sheet_path.startswith('xl/'):
                    sheet_path = 'xl/' + sheet_path
                if sheet_path not in z.namelist():
                    continue

                sheet_xml = z.read(sheet_path)
                sheet_root = ET.fromstring(sheet_xml)

                # 解析行数据
                rows_data = {}
                for row_elem in sheet_root.findall('.//s:row', ns):
                    row_num = int(row_elem.get('r', '0'))
                    cells = {}
                    for c in row_elem.findall('s:c', ns):
                        col_ref = c.get('r', '')
                        col_letter = re.match(r'([A-Z]+)', col_ref).group(1) if col_ref else ''
                        cell_type = c.get('t', '')
                        value_elem = c.find('s:v', ns)
                        inline_elem = c.find('.//s:is/s:t', ns)

                        cell_value = ''
                        if value_elem is not None and value_elem.text:
                            if cell_type == 's' and value_elem.text.isdigit():
                                idx = int(value_elem.text)
                                if idx < len(shared_strings):
                                    cell_value = shared_strings[idx]
                                else:
                                    cell_value = value_elem.text
                            else:
                                cell_value = value_elem.text
                        elif inline_elem is not None and inline_elem.text:
                            cell_value = inline_elem.text

                        cells[col_letter] = cell_value

                    if cells:
                        rows_data[row_num] = cells

                if not rows_data:
                    continue

                # L4: 处理合并单元格 —— 将合并区域左上角的值回填到所有被合并坐标，
                # 避免双行/多级表头因合并导致子表头列名丢失而错位
                try:
                    merge_cells = sheet_root.find('.//s:mergeCells', ns)
                    if merge_cells is not None:
                        for mc in merge_cells.findall('s:mergeCell', ns):
                            ref = mc.get('ref', '')
                            if ':' not in ref:
                                continue
                            top_left, bottom_right = ref.split(':')
                            tl_col = re.match(r'([A-Z]+)', top_left)
                            tl_row = re.search(r'(\d+)', top_left)
                            br_col = re.match(r'([A-Z]+)', bottom_right)
                            br_row = re.search(r'(\d+)', bottom_right)
                            if not (tl_col and tl_row and br_col and br_row):
                                continue
                            tl_col, tl_row = tl_col.group(1), int(tl_row.group(1))
                            br_col, br_row = br_col.group(1), int(br_row.group(1))
                            # 取左上角值
                            val = ''
                            for rn in range(tl_row, br_row + 1):
                                rc = rows_data.get(rn)
                                if rc and tl_col in rc:
                                    val = rc[tl_col]
                                    break
                            if not val:
                                continue
                            # 回填到所有被合并坐标
                            for rn in range(tl_row, br_row + 1):
                                rc = rows_data.setdefault(rn, {})
                                for cidx in _col_range(tl_col, br_col):
                                    if not rc.get(cidx):
                                        rc[cidx] = val
                except Exception as e:
                    logger.warning(f"合并单元格处理跳过: {e}")

                # 从行数据构建列序
                max_row = max(rows_data.keys())
                # 收集所有出现过的列字母（仅非空值，避免空列干扰列序）
                all_cols = set()
                for row_cells in rows_data.values():
                    for col_letter, val in row_cells.items():
                        if val:
                            all_cols.add(col_letter)
                # 按列索引排序（A=1, B=2, ..., Z=26, AA=27, AB=28...）
                def col_to_index(col: str) -> int:
                    idx = 0
                    for c in col:
                        idx = idx * 26 + (ord(c) - ord('A') + 1)
                    return idx
                sorted_cols = sorted(all_cols, key=col_to_index)

                # 提取前几行作为表头候选
                candidate_rows = []
                for rn in range(1, min(max_row + 1, 8)):
                    cells = rows_data.get(rn, {})
                    row_vals = [normalize_cell(cells.get(c, '')) for c in sorted_cols]
                    candidate_rows.append(row_vals)

                # 定位最佳表头行
                header_row_idx, merged_headers, is_double = _locate_header(candidate_rows)

                # 提取数据行（双行表头且主表头被选中时数据从+3起，否则+2）
                data_start = header_row_idx + (3 if is_double and header_row_idx == 0 else 2)
                data_rows = []
                for rn in range(data_start, max_row + 1):
                    cells = rows_data.get(rn, {})
                    row_dict = {}
                    has_data = False
                    for ci, col in enumerate(sorted_cols):
                        val = normalize_cell(cells.get(col, ''))
                        if ci < len(merged_headers):
                            h = merged_headers[ci]
                            if h:
                                row_dict[h] = val
                                if val:
                                    has_data = True
                    if has_data and row_dict:
                        row_dict['_row_index'] = rn
                        data_rows.append(row_dict)

                sheets.append(ParsedSheet(
                    index=sheet_id,
                    name=sheet_name,
                    headers=merged_headers,
                    rows=data_rows,
                ))

    except zipfile.BadZipFile:
        raise ValueError("文件格式错误：不是有效的xlsx文件")
    except Exception as e:
        logger.error(f"xlsx解析失败: {e}")
        raise

    return sheets


def read_csv(file_content: bytes) -> List[ParsedSheet]:
    """解析CSV文件，自动检测编码和分隔符"""
    # 检测编码
    encoding = _detect_encoding(file_content)
    text = file_content.decode(encoding, errors='replace')

    # 检测分隔符
    delimiter = _detect_delimiter(text)

    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    rows = list(reader)
    if not rows:
        return []

    # 第一行为表头
    headers = [normalize_cell(h) for h in rows[0]]
    data_rows = []
    for row in rows[1:]:
        row_dict = {}
        has_data = False
        for i, val in enumerate(row):
            if i < len(headers) and headers[i]:
                row_dict[headers[i]] = normalize_cell(val)
                if val.strip():
                    has_data = True
        if has_data:
            data_rows.append(row_dict)

    # CSV只有一个"sheet"
    return [ParsedSheet(index=0, name="CSV数据", headers=headers, rows=data_rows)]


# =============================================================================
# 编码与分隔符检测
# =============================================================================

def _detect_encoding(data: bytes) -> str:
    """检测CSV文件编码"""
    if data[:3] == b'\xef\xbb\xbf':
        return 'utf-8-sig'
    if data[:2] == b'\xff\xfe':
        return 'utf-16-le'
    if data[:2] == b'\xfe\xff':
        return 'utf-16-be'
    # 尝试常见编码
    for enc in ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1']:
        try:
            data.decode(enc)
            return enc
        except (UnicodeDecodeError, UnicodeError):
            continue
    return 'utf-8'


def _detect_delimiter(text: str) -> str:
    """检测CSV分隔符"""
    lines = text.strip().split('\n')
    if not lines:
        return ','
    first_line = lines[0]
    # 统计各种分隔符的出现次数
    counts = {
        ',': first_line.count(','),
        '\t': first_line.count('\t'),
        ';': first_line.count(';'),
        '|': first_line.count('|'),
    }
    # 选择出现最多的分隔符（但排除0）
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ','


# =============================================================================
# 表头定位
# =============================================================================

def _col_letter_to_num(col: str) -> int:
    """列字母转序号: A=1, Z=26, AA=27"""
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch.upper()) - ord('A') + 1)
    return n


def _num_to_col_letter(n: int) -> str:
    """序号转列字母"""
    s = ''
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(ord('A') + r) + s
    return s


def _col_range(start_col: str, end_col: str):
    """生成 [start_col, end_col] 闭区间的所有列字母（含多级表头跨列合并）"""
    a, b = _col_letter_to_num(start_col), _col_letter_to_num(end_col)
    return [_num_to_col_letter(i) for i in range(min(a, b), max(a, b) + 1)]


def _locate_header(candidate_rows: List[List[str]]) -> Tuple[int, List[str], bool]:
    """扫描前几行，选择最佳表头行
    返回: (选中行索引 0-based, 合并后的列名列表, 是否双行表头)
    """
    if not candidate_rows:
        return 0, [], False

    # 收集所有已知列别名
    all_known_aliases = set()
    for config in SHEET_TYPE_REGISTRY.values():
        for alias_list in config.values():
            if isinstance(alias_list, list):
                for a in alias_list:
                    if a:
                        all_known_aliases.add(a.lower().strip())

    # 对每行评分
    best_idx = 0
    best_score = -1

    for i, row in enumerate(candidate_rows):
        score = 0
        for cell in row:
            if cell and cell.lower().strip() in all_known_aliases:
                score += 1
            # 数字少的是表头（数字多的可能是数据行）
            if cell and not cell.replace('.', '').replace('-', '').isdigit():
                score += 0.5

        if score > best_score:
            best_score = score
            best_idx = i

    # 合并双行表头：合成"父/子"唯一键
    headers = list(candidate_rows[best_idx])
    is_double = False
    if best_idx + 1 < len(candidate_rows):
        next_row = candidate_rows[best_idx + 1]
        # 判断下一行是否为子表头行（非数据行）
        # 子表头行特征：非空单元格中，至少 2 个值匹配已知列别名
        next_non_empty = [v for v in next_row if v]
        if next_non_empty:
            alias_match_count = sum(1 for v in next_non_empty if v.lower().strip() in all_known_aliases)
            is_subheader = alias_match_count >= 2
        else:
            is_subheader = False

        if is_subheader:
            for j in range(len(headers)):
                if j < len(next_row) and next_row[j]:
                    parent = headers[j] or ''
                    child = next_row[j]
                    if parent and child and child != parent:
                        # 合成"父/子"唯一键，如"联系方式/电话"、"客户简单信息/评论内容要点"
                        headers[j] = f"{parent}/{child}"
                        is_double = True
                    elif not parent and child:
                        # 仅子表头存在
                        headers[j] = child
                        is_double = True
                    # parent == child 时保持 parent 不变，不设 is_double

    return best_idx, headers, is_double


# =============================================================================
# Sheet类型识别
# =============================================================================

def detect_sheet_type(sheet_name: str, headers: List[str]) -> str:
    """根据表名和列名识别Sheet类型
    返回: education/douyin_ops/moment_ad/live_lead/schedule/operational/unknown
    """
    name_lower = sheet_name.lower().strip() if sheet_name else ''
    header_lower = set(str(h).lower().strip() for h in headers if h)

    # 按优先级顺序匹配
    for stype in SHEET_TYPE_ORDER:
        config = SHEET_TYPE_REGISTRY[stype]

        # 表名匹配
        name_match = any(kw.lower() in name_lower for kw in config.get("name_keywords", []))

        # 列签名匹配
        sig_matches = sum(
            1 for sig in config.get("header_signatures", [])
            if any(sig.lower() in hl for hl in header_lower)
        )

        # 排班表和运营表按表名+列签名双重匹配
        if config.get("is_operational"):
            if name_match and sig_matches >= 1:
                return stype
            continue

        # 有联系方式的表
        if sig_matches >= 2:
            return stype
        if name_match and sig_matches >= 1:
            return stype

    return "unknown"


# =============================================================================
# 字段归一化
# =============================================================================

def normalize_cell(value: Any) -> str:
    """归一化单元格值"""
    if value is None:
        return ''
    s = str(value).strip()
    # 处理 "None" / "none" / "NULL" / "无" 等空值表示
    if s.lower() in ('none', 'null', 'nan', 'n/a', 'na', '无', '空', '-'):
        return ''
    return s


def normalize_contact(contact: str) -> str:
    """归一化联系方式：去空格、横杠、括号，剥离常见中文前缀"""
    s = normalize_cell(contact)
    if not s:
        return ''
    # 去空格和特殊字符
    s = re.sub(r'[\s\-\(\)（）\- ]', '', s)
    # 剥离常见中文前缀（如"微信"、"电话"、"手机号"等），
    # 避免"微信1036528777"类有效号码被汉字过滤误杀
    s = re.sub(r'^(微信|电话|手机号|手机|联系方式|联系电话)\s*', '', s)
    return s


# 汉字检测正则
_HAN_RE = re.compile(r'[一-鿿㐀-䶿]')

def has_chinese(text: str) -> bool:
    """检测字符串是否包含汉字"""
    if not text:
        return False
    return bool(_HAN_RE.search(text))


def build_dedup_key(contact: str, wechat: str) -> str:
    """构建去重键：contact_norm||wechat_norm
    如果contact和wechat都为空，返回空字符串（表示无法去重）
    """
    contact_norm = normalize_contact(contact)
    wechat_norm = normalize_cell(wechat)
    if not contact_norm and not wechat_norm:
        return ''
    return f"{contact_norm}||{wechat_norm}"


def convert_excel_serial_date(value: Any) -> str:
    """将Excel序列号日期转为日期字符串
    Excel epoch: 1899-12-30 (因为1900-02-29的bug)
    """
    try:
        val = float(value)
        if val > 1 and val < 200000:  # 合理日期范围
            epoch = datetime(1899, 12, 30)
            dt = epoch + timedelta(days=val)
            return dt.strftime("%Y-%m-%d")
        if 0 < val <= 1:  # 时间（小数部分）
            total_seconds = val * 86400
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            seconds = int(total_seconds % 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        pass
    return str(value)


def extract_period_from_date(date_str: str) -> str:
    """从日期字符串提取 YYYY-MM 格式的月标识"""
    if not date_str:
        return ''
    # 尝试匹配 YYYY-MM-DD
    m = re.match(r'(\d{4})-(\d{2})', date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # 尝试匹配 MM-DD
    m = re.match(r'(\d{2})-(\d{2})', date_str)
    if m:
        return ''  # 缺少年份，无法确定
    return ''


def find_column(headers: List[str], aliases: List[str]) -> Optional[int]:
    """在表头列表中查找匹配别名的列索引"""
    if not aliases:
        return None
    header_lower = [str(h).lower().strip() for h in headers]
    for alias in aliases:
        alias_lower = alias.lower().strip()
        for i, h in enumerate(header_lower):
            if alias_lower == h or alias_lower in h:
                return i
    return None


# =============================================================================
# 预留行检测
# =============================================================================

TRIVIAL_SUBJECTS = {
    '序号', '星期', '直播人员', '留资方式', '互动场景', '招生老师',
    '投放账户', '单元名称', '单元ID', '留资路径', '用户昵称',
    '运营值班人员', '日期', '统计', '分配日', '分配月', '序号',
    '原咨询反馈', '提升形式', '第一次跟进', '第二次跟进', '第三次跟进',
    '一次跟进', '二次跟进', '三次跟进', '数据状态与标签', '数据状态',
    '状态标签', '跟进状态', '跟进方式', '老师', '跟进老师',
}

def _is_reserved_template(rec: dict, contact_norm: str, wechat_norm: str) -> bool:
    """判断是否仅为预留行（无联系方式，仅含元数据字段）
    当 contact 和 wechat 都为空，且记录中所有非空字段都属于 TRIVIAL_SUBJECTS 时，
    判定为预留行。
    支持"父/子"格式 key（如"招生老师反馈/提升形式"），提取子字段名进行匹配。
    """
    if contact_norm or wechat_norm:
        return False
    for key, val in rec.items():
        if key.startswith('_'):
            continue
        if val:
            # 分解"父/子"格式 key，提取子字段名进行匹配
            parts = key.split('/')
            key_match = any(p in TRIVIAL_SUBJECTS for p in parts if p)
            if not key_match:
                return False  # 有实质性业务字段 → 不是预留行
    return True


# =============================================================================
# 去重引擎
# =============================================================================

def dedup_check(records: List[Dict], db, sheet_type: str, global_dedup: bool = False) -> Tuple[List[Dict], List[Dict]]:
    """检查重复记录
    返回: (to_insert, skips)
    - to_insert: 无重复的可插入记录（已添加dedup_key）
    - skips: 重复记录列表（含reason）
    - global_dedup: False(默认)=按 sheet_type 分表去重(保守策略,避免跨渠道误合并);
                     True=跨表全局去重(业务确认同一人需合并时启用)
    """
    from models import MultiDimRecord

    to_insert = []
    skips = []
    config = SHEET_TYPE_REGISTRY.get(sheet_type, {})

    # 如果该类型无联系方式，不做去重
    if not config.get("has_contact", True):
        for rec in records:
            rec['_dedup_key'] = ''
            to_insert.append(rec)
        return to_insert, skips

    for rec in records:
        # 提取联系方式
        contact = ''
        wechat = ''

        contact_idx = find_column(list(rec.keys()), config.get("contact_col_aliases", []))
        wechat_idx = find_column(list(rec.keys()), config.get("wechat_col_aliases", []))

        if contact_idx is not None:
            col_name = list(rec.keys())[contact_idx]
            raw_contact = rec.get(col_name, '')
            # 处理 ";" / "；" 分隔的电话+微信格式
            if ';' in raw_contact or '；' in raw_contact:
                parts = raw_contact.replace('；', ';').split(';', 1)
                contact = parts[0].strip()
                if not wechat and len(parts) > 1:
                    wechat = parts[1].strip()
            else:
                contact = raw_contact
        if wechat_idx is not None:
            col_name = list(rec.keys())[wechat_idx]
            raw_wechat = rec.get(col_name, '')
            if not wechat:
                wechat = raw_wechat

        # 先归一化，用于后续检测
        contact_norm = normalize_contact(contact)
        wechat_norm = normalize_cell(wechat)

        # 汉字检测：联系方式含汉字则过滤
        if has_chinese(contact_norm) or has_chinese(wechat_norm):
            skips.append({
                **rec,
                '_dedup_key': '',
                '_contact_norm': contact_norm,
                '_wechat_norm': wechat_norm,
                '_skip_reason': 'invalid_contact',
                '_skip_detail': '联系方式含汉字，已过滤'
            })
            continue

        # 预留行检测：无联系方式且仅含元数据字段
        if _is_reserved_template(rec, contact_norm, wechat_norm):
            skips.append({
                **rec,
                '_dedup_key': '',
                '_contact_norm': contact_norm,
                '_wechat_norm': wechat_norm,
                '_skip_reason': 'template_empty',
                '_skip_detail': '预留/提前数据，仅含元数据字段，已过滤'
            })
            continue

        dedup_key = build_dedup_key(contact, wechat)

        # 无联系方式时标记跳过
        if not dedup_key:
            skips.append({
                **rec,
                '_dedup_key': '',
                '_contact_norm': contact_norm,
                '_wechat_norm': wechat_norm,
                '_skip_reason': 'missing_contact',
                '_skip_detail': '缺少联系方式和微信，无法去重'
            })
            continue

        rec['_dedup_key'] = dedup_key
        rec['_contact_norm'] = contact_norm
        rec['_wechat_norm'] = wechat_norm

        # 查数据库
        q = db.query(MultiDimRecord).filter(MultiDimRecord.dedup_key == dedup_key)
        if not global_dedup:
            q = q.filter(MultiDimRecord.sheet_type == sheet_type)
        exists = q.first()

        if exists:
            skips.append({
                **rec,
                '_skip_reason': 'duplicate',
                '_skip_detail': f'联系方式+微信组合已存在 (id={exists.id})'
            })
        else:
            to_insert.append(rec)

    return to_insert, skips


# =============================================================================
# 主解析入口
# =============================================================================

def parse_file(file_content: bytes, filename: str) -> List[ParsedSheet]:
    """解析文件入口，自动识别格式"""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''

    if ext in ('xlsx', 'xls'):
        return read_xlsx(file_content)
    elif ext == 'csv':
        return read_csv(file_content)
    else:
        raise ValueError(f"不支持的文件格式: .{ext}（仅支持 .xlsx, .xls, .csv）")


def process_sheets(sheets: List[ParsedSheet], db) -> dict:
    """处理所有sheet，执行类型识别、字段映射、去重检查
    返回: {
        sheets: [{type, name, total, will_insert, will_skip, sample_skips, headers}],
        summary: {total, total_insert, total_skip, by_type}
    }
    """
    result_sheets = []
    total = 0
    total_insert = 0
    total_skip = 0
    by_type = {}
    skip_by_reason = {}

    for sheet in sheets:
        stype = detect_sheet_type(sheet.name, sheet.headers)
        config = SHEET_TYPE_REGISTRY.get(stype, {})

        to_insert, skips = dedup_check(sheet.rows, db, stype)

        # 统计跳过原因分布
        for s in skips:
            reason = s.get("_skip_reason", "unknown")
            skip_by_reason[reason] = skip_by_reason.get(reason, 0) + 1

        sample_skips = []
        for s in skips[:5]:
            sample_skips.append({
                'row_index': s.get('_row_index', 0),
                'contact_norm': s.get('_contact_norm', ''),
                'wechat_norm': s.get('_wechat_norm', ''),
                'reason': s.get('_skip_reason', ''),
                'detail': s.get('_skip_detail', ''),
            })

        sheet_info = {
            'index': sheet.index,
            'name': sheet.name,
            'type': stype,
            'headers': sheet.headers,
            'total_rows': len(sheet.rows),
            'will_insert': len(to_insert),
            'will_skip': len(skips),
            'sample_skips': sample_skips,
            'is_operational': config.get("is_operational", False),
        }
        result_sheets.append(sheet_info)

        total += len(sheet.rows)
        total_insert += len(to_insert)
        total_skip += len(skips)
        by_type[stype] = by_type.get(stype, 0) + len(sheet.rows)

    return {
        'sheets': result_sheets,
        'summary': {
            'total': total,
            'total_insert': total_insert,
            'total_skip': total_skip,
            'by_type': by_type,
            'skip_by_reason': skip_by_reason,
        },
    }


def sync_record_to_lead(rec: Dict, db, sheet_type: str) -> bool:
    """将多维导入记录同步到统一线索表 ApiClue
    仅对含联系方式的业务表(education/douyin_ops/moment_ad/live_lead)生效；
    schedule/operational 由 sync_schedule_to_plan 处理，此处跳过。
    使用 (phone_decrypted, weixin_manual) 组合查重，避免向 api_clues 灌入重复。
    返回: True=已同步, False=跳过(无联系方式/非业务表/已存在)
    """
    from models import ApiClue

    config = SHEET_TYPE_REGISTRY.get(sheet_type, {})
    if not config.get("has_contact", True):
        return False

    contact = rec.get("_contact_norm", "")
    weixin = rec.get("_wechat_norm", "")
    if not contact and not weixin:
        return False

    # 查重：同一联系方式+微信在 api_clues 中已存在则跳过
    exists = db.query(ApiClue).filter(
        ApiClue.phone_decrypted == (contact or None),
        ApiClue.weixin_manual == (weixin or None),
    ).first()
    if exists:
        return False

    name = rec.get("name", "")
    assign_date = rec.get("assign_date", "")
    teacher = rec.get("assigned_teacher", "")
    status = rec.get("data_status", "")

    import uuid

    # 根据 sheet_type 推导来源语义
    # education/douyin_ops/moment_ad → 来自多维导入
    # live_lead → 来自直播数据分配
    source_map = {
        'education': 'multidim_education',
        'douyin_ops': 'multidim_douyin',
        'moment_ad': 'multidim_moment',
        'live_lead': 'multidim_live',
    }
    actual_source = source_map.get(sheet_type, 'multidim')

    # 根据字段内容推导流量类型
    raw = {k: v for k, v in rec.items() if not k.startswith('_')}
    flow_type = None
    flow_entrance = rec.get('flow_entrance', '') or ''
    for key, val in raw.items():
        if '投放' in key or '广告' in key or '账户' in key:
            flow_type = 'marketing'
            break
        if '自然' in str(val) or '自然' in key:
            flow_type = 'natural'
            break
    if not flow_type and '直播' in str(raw):
        flow_type = 'live'

    new_clue = ApiClue(
        clue_id=f"multidim_{sheet_type}_{uuid.uuid4().hex}",
        name=name,
        phone_decrypted=contact or None,
        weixin_manual=weixin or None,
        create_time_detail=assign_date or None,
        lead_time=assign_date or None,
        advertiser_name=teacher or None,
        clue_type=status or None,
        clue_source=actual_source,
        flow_type=flow_type,
        flow_entrance=flow_entrance or None,
        raw_data=json.dumps(raw, ensure_ascii=False),
        created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(new_clue)
    return True


def _find_schedule_col(rec: Dict, aliases: List[str]) -> str:
    """在记录中按别名查找第一个非空值"""
    for alias in aliases:
        for k, v in rec.items():
            if k and alias and alias.lower() in str(k).lower() and v:
                return str(v)
    return ''


def sync_schedule_to_plan(rec: Dict, db, sheet_type: str, batch_id: int) -> bool:
    """将排班类(schedule/operational)记录同步到排班系统
    策略：为导入的每一天创建独立 SchedulePlan（标记来源批次），
    再建 ScheduleBinding(date=导入日期, plan_id=新plan)，使运营在排班日历按日期可见。
    直播人员/直播时间/营销消耗等写入 plan.notes 与 BindingSlot 便于追溯。
    返回: True=已同步, False=缺日期等跳过
    """
    from models import SchedulePlan, ScheduleBinding, ScheduleSlot, BindingSlot

    date_val = _find_schedule_col(rec, ["日期", "分配日", "分配月"])
    if not date_val:
        return False
    # 归一化日期：支持 YYYY-MM-DD / MM-DD / M.D / MM.DD 等排班表常见格式
    date_norm = date_val.strip().replace('/', '-').replace('.', '-')
    m = re.match(r'(\d{4})-(\d{1,2})-(\d{1,2})', date_norm)
    if m:
        date_norm = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    else:
        m = re.match(r'(\d{1,2})-(\d{1,2})', date_norm)
        if m:
            # 缺少年份，补当前年份
            year = datetime.now().year
            date_norm = f"{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
        else:
            return False

    # 避免重复：同日期已存在绑定则跳过
    exist = db.query(ScheduleBinding).filter(ScheduleBinding.date == date_norm).first()
    if exist:
        return False

    room_val = _find_schedule_col(rec, ["直播人员", "人员", "运营值班人员", "值班人员"])
    time_val = _find_schedule_col(rec, ["直播时间", "时间"])
    cost_val = _find_schedule_col(rec, ["营销消耗", "日消耗"])

    plan_name = f"导入排班-{date_norm}"
    plan = SchedulePlan(
        name=plan_name,
        start_time="00:00",
        end_time="23:59",
        time_granularity=60,
        room_count=1,
        anchor_count=1,
        is_active=True,
        notes=json.dumps({
            "source": "multidim_import",
            "batch_id": batch_id,
            "sheet_type": sheet_type,
            "room": room_val,
            "live_time": time_val,
            "cost": cost_val,
            "raw": {k: v for k, v in rec.items() if not k.startswith('_')},
        }, ensure_ascii=False),
    )
    db.add(plan)
    db.flush()

    # 建一个默认槽位承载直播人员/时间信息
    slot = ScheduleSlot(
        plan_id=plan.id,
        time_slot="00:00-23:59",
        room_index=1,
        slot_status="on_air_anchor",
        anchor_slot=None,
    )
    db.add(slot)

    binding = ScheduleBinding(
        date=date_norm,
        plan_id=plan.id,
        anchor_mapping=json.dumps({"1": room_val}, ensure_ascii=False),
    )
    db.add(binding)
    db.flush()  # 立即持久化，确保后续同日期行能通过 exist 检测（L885）查到
    return True


def import_sheets(sheets: List[ParsedSheet], db, filename: str, file_format: str, admin_name: str) -> Dict:
    """执行导入：写入数据库，创建批次日志
    返回: {inserted_count, skipped_count, error_count, batch_id}
    """
    from models import MultiDimRecord, MultiDimImportBatch, MultiDimImportSkip

    batch = MultiDimImportBatch(
        filename=filename,
        file_format=file_format,
        admin_name=admin_name,
        status="success",
        imported_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    db.add(batch)
    db.flush()

    total_inserted = 0
    total_skipped = 0
    total_errors = 0
    schedule_bindings_created = 0
    by_type = {}

    for sheet in sheets:
        stype = detect_sheet_type(sheet.name, sheet.headers)
        config = SHEET_TYPE_REGISTRY.get(stype, {})

        to_insert, skips = dedup_check(sheet.rows, db, stype)

        # 写入跳过的记录
        for s in skips:
            skip = MultiDimImportSkip(
                batch_id=batch.id,
                sheet_type=stype,
                sheet_name=sheet.name,
                row_index=s.get('_row_index', 0),
                contact_norm=s.get('_contact_norm', ''),
                wechat=s.get('_wechat_norm', ''),
                reason=s.get('_skip_reason', 'missing_contact'),
                detail=s.get('_skip_detail', ''),
                raw_data=json.dumps(s, ensure_ascii=False),
            )
            db.add(skip)
            total_skipped += 1

        # 写入新记录
        for rec in to_insert:
            # 提取字段
            contact = rec.get('_contact_norm', '')
            wechat = rec.get('_wechat_norm', '')
            dedup_key = rec.get('_dedup_key', '')

            # 提取姓名
            name = ''
            name_idx = find_column(list(rec.keys()), config.get("name_col_aliases", []))
            if name_idx is not None:
                col_name = list(rec.keys())[name_idx]
                name = rec.get(col_name, '')

            # 提取分配日期
            assign_date = ''
            date_idx = find_column(list(rec.keys()), config.get("date_col_aliases", []))
            if date_idx is not None:
                col_name = list(rec.keys())[date_idx]
                raw_date = rec.get(col_name, '')
                # 尝试转换Excel序列号
                assign_date = convert_excel_serial_date(raw_date)

            # 提取招生老师
            teacher = ''
            teacher_idx = find_column(list(rec.keys()), config.get("teacher_col_aliases", []))
            if teacher_idx is not None:
                col_name = list(rec.keys())[teacher_idx]
                teacher = rec.get(col_name, '')

            # 提取数据状态
            status = ''
            status_idx = find_column(list(rec.keys()), config.get("status_col_aliases", []))
            if status_idx is not None:
                col_name = list(rec.keys())[status_idx]
                status = rec.get(col_name, '')

            # 提取period
            period = ''
            if assign_date:
                period = extract_period_from_date(assign_date)
            if not period:
                # 尝试从其他日期列提取
                date_idx = find_column(list(rec.keys()), config.get("date_col_aliases", []))
                if date_idx is not None:
                    col_name = list(rec.keys())[date_idx]
                    period = extract_period_from_date(rec.get(col_name, ''))

            # 清理辅助字段
            clean_rec = {k: v for k, v in rec.items() if not k.startswith('_')}

            # 将提取到的标准化字段写回 rec，供 sync_record_to_lead 等下游函数使用
            rec['name'] = name
            rec['assign_date'] = assign_date
            rec['assigned_teacher'] = teacher
            rec['data_status'] = status

            record = MultiDimRecord(
                sheet_type=stype,
                period=period,
                source_file=filename,
                batch_id=batch.id,
                contact_norm=contact,
                wechat=wechat,
                dedup_key=dedup_key,
                name=name,
                assign_date=assign_date,
                assigned_teacher=teacher,
                data_status=status,
                raw_data=json.dumps(clean_rec, ensure_ascii=False),
                row_index=rec.get('_row_index', 0),
            )
            db.add(record)
            total_inserted += 1

            # L1: 同步到统一线索体系 ApiClue（仅含联系方式的业务表）
            try:
                if sync_record_to_lead(rec, db, stype):
                    record.synced_to_lead = 1
            except Exception as e:
                db.rollback()
                logger.error(f"同步到线索体系失败(sheet={stype}, row={rec.get('_row_index')}): {e}")

            # L2: 排班类数据已存入 MultiDimRecord，不再同步到 SchedulePlan/ScheduleSlot
            # 排班数据在导入日志中可查看，不再创建冗余的排班方案

        by_type[stype] = {
            'inserted': len(to_insert),
            'skipped': len(skips),
        }

    # 更新批次统计
    batch.total_rows = total_inserted + total_skipped
    batch.inserted_count = total_inserted
    batch.skipped_count = total_skipped
    batch.by_type_json = json.dumps(by_type, ensure_ascii=False)

    db.commit()
    db.refresh(batch)

    return {
        'inserted_count': total_inserted,
        'skipped_count': total_skipped,
        'error_count': total_errors,
        'batch_id': batch.id,
        'by_type': by_type,
        'schedule_bindings_created': schedule_bindings_created,
    }

