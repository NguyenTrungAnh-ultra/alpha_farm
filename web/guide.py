"""
Parser and view builders of the /guide page: a checklist read from a markdown file of tables and the timeline drawn from it.

The checklist file is a list of `## section` headings, each followed by a table of exactly five columns
(task | group | deadline | status | note). A deadline is `YYYY-MM-DD`, a range `YYYY-MM-DD → YYYY-MM-DD` or a dash.
Only the first section holds the department's own deadlines; the sections named in thesis.GUIDE_SUGGESTED_SECTIONS hold
suggested deadlines. A row that cannot be parsed is kept without a date and carries a warning, never an exception.
"""

import datetime
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from markupsafe import Markup, escape

from web import thesis

TIMEZONE = 'Asia/Ho_Chi_Minh'
COLUMNS = 5
# Both files are re-read on every request so edits show without a restart.
CHECKLIST_FILE = 'THESIS_CHECKLIST.md'
GUIDE_FILE = 'THESIS_GUIDE.md'

STATUS_BY_SYMBOL = {'✅': 'done', '🔧': 'progress', '⏸': 'waiting', '⛔': 'blocked', 'chưa': 'todo'}
_DATE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
_RANGE_SEPARATOR = re.compile(r'\s*(?:→|->)\s*')
_NO_DATE = {'', '—', '–', '-'}
_VARIATION_SELECTOR = '️'

# Timeline geometry in viewBox units: the card scrolls sideways below this width on a phone.
WIDTH = 900
LEFT = 120
RIGHT = 14
PAD_DAYS = 5
HEADER = 40
SUBROW = 22
LANE_GAP = 12
CHAR_WIDTH = 5.8
LABEL_CHARS = 34


def today_in_zone(zone: str = TIMEZONE) -> datetime.date:
    """Current calendar date in the thesis time zone (a fixed UTC+7 offset when tzdata is missing)."""
    try:
        tz = ZoneInfo(zone)
    except ZoneInfoNotFoundError:
        tz = datetime.timezone(datetime.timedelta(hours=7))
    return datetime.datetime.now(tz).date()


@dataclass
class Row:
    task: str
    group: str
    due_text: str
    status: str
    note: str
    start: Optional[datetime.date] = None
    end: Optional[datetime.date] = None
    warning: str = ''


@dataclass
class Section:
    title: str
    intro: str
    official: bool
    suggested: bool
    rows: List[Row] = field(default_factory=list)


def read_text(directory: str, name: str) -> Optional[str]:
    """File text, or None when it is missing or unreadable."""
    try:
        with open(os.path.join(directory, name), encoding='utf-8-sig') as handle:
            return handle.read()
    except OSError:
        return None


def parse_status(text: str) -> Optional[str]:
    cleaned = text.replace(_VARIATION_SELECTOR, '').strip().strip('`').strip()
    return STATUS_BY_SYMBOL.get(cleaned) or STATUS_BY_SYMBOL.get(cleaned.casefold())


def parse_deadline(text: str) -> Tuple[Optional[datetime.date], Optional[datetime.date], str]:
    """(start, end, warning): a single date has start == end; a dash has neither and no warning."""
    cleaned = text.strip().strip('`').strip()
    if cleaned in _NO_DATE:
        return None, None, ''
    parts = _RANGE_SEPARATOR.split(cleaned)
    if len(parts) > 2 or not all(_DATE.match(p) for p in parts):
        return None, None, f'ngày không đọc được: "{cleaned}"'
    try:
        dates = [datetime.date.fromisoformat(p) for p in parts]
    except ValueError:
        return None, None, f'ngày không hợp lệ: "{cleaned}"'
    if len(dates) == 2 and dates[1] < dates[0]:
        return None, None, f'khoảng ngày ngược: "{cleaned}"'
    return dates[0], dates[-1], ''


def split_cells(line: str) -> List[str]:
    body = line.strip()
    body = body[1:] if body.startswith('|') else body
    body = body[:-1] if body.endswith('|') else body
    return [cell.strip() for cell in body.split('|')]


def _is_separator(cells: List[str]) -> bool:
    return all(re.fullmatch(r':?-{3,}:?', c) for c in cells if c) and any(cells)


def parse_row(cells: List[str]) -> Row:
    task, group, due_text, status_text, note = cells
    start, end, warning = parse_deadline(due_text)
    status = parse_status(status_text)
    if status is None:
        warning = (warning + '; ' if warning else '') + f'trạng thái lạ: "{status_text}"'
        status = 'todo'
    return Row(task, group, due_text.strip(), status, note, start, end, warning)


def parse_checklist(text: str) -> Tuple[List[Section], List[str]]:
    """Sections in file order and the warnings that belong to no single row (a table row with the wrong column count)."""
    sections: List[Section] = []
    problems: List[str] = []
    current: Optional[Section] = None
    in_table = False
    header_seen = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith('## '):
            title = stripped[3:].strip()
            current = Section(title, '', official=not sections, suggested=title in thesis.GUIDE_SUGGESTED_SECTIONS)
            sections.append(current)
            in_table = header_seen = False
        elif current is None:
            continue
        elif stripped.startswith('|'):
            in_table = True
            cells = split_cells(stripped)
            if _is_separator(cells):
                continue
            if not header_seen:
                header_seen = True
                continue
            if len(cells) != COLUMNS:
                problems.append(f'mục "{current.title}": dòng bảng có {len(cells)} cột, cần {COLUMNS}: {stripped[:60]}')
                continue
            current.rows.append(parse_row(cells))
        elif stripped and not in_table and not stripped.startswith('#'):
            current.intro = (current.intro + ' ' + stripped).strip()
    return sections, problems


def all_warnings(sections: List[Section], problems: List[str]) -> List[str]:
    return problems + [f'{r.task}: {r.warning}' for s in sections for r in s.rows if r.warning]


def days_left(row: Row, today: datetime.date) -> Optional[int]:
    """Days from today to the row's deadline (the end of a range); negative when past; None without a date."""
    return None if row.end is None else (row.end - today).days


def is_overdue(row: Row, today: datetime.date) -> bool:
    """A dated row whose deadline is before today and which is not done."""
    left = days_left(row, today)
    return left is not None and left < 0 and row.status != 'done'


def countdown_text(row: Row, today: datetime.date) -> str:
    """'còn N ngày' / 'hôm nay' / 'quá hạn N ngày' for a dated, undone row; empty otherwise."""
    left = days_left(row, today)
    if left is None or row.status == 'done':
        return ''
    if left < 0:
        return f'quá hạn {-left} ngày'
    return 'hôm nay' if left == 0 else f'còn {left} ngày'


def next_official(sections: List[Section], today: datetime.date) -> Optional[Row]:
    """The official deadline not yet done and not yet past that comes first; on a tie a single date beats a range."""
    if not sections:
        return None
    pool = [(r.end, r.start != r.end, i, r) for i, r in enumerate(sections[0].rows)
            if r.end is not None and r.status != 'done' and r.end >= today]
    return min(pool, key=lambda p: p[:3])[3] if pool else None


def submission_row(sections: List[Section]) -> Optional[Row]:
    """The official single-date row of the thesis submission."""
    target = datetime.date.fromisoformat(thesis.THESIS_SUBMISSION_DATE)
    if not sections:
        return None
    return next((r for r in sections[0].rows if r.start == r.end == target), None)


def status_counts(sections: List[Section]) -> List[Dict]:
    counts = {key: 0 for key in thesis.GUIDE_STATUS_LABELS}
    for section in sections:
        for row in section.rows:
            counts[row.status] += 1
    return [{'key': key, 'label': thesis.GUIDE_STATUS_LABELS[key], 'symbol': thesis.GUIDE_STATUS_SYMBOLS[key], 'count': n}
            for key, n in counts.items()]


def format_date(date: Optional[datetime.date]) -> str:
    return date.strftime('%d/%m/%Y') if date else ''


def due_label(row: Row) -> str:
    if row.start is None:
        return ''
    return format_date(row.start) if row.start == row.end else f'{format_date(row.start)} → {format_date(row.end)}'


_LINK = re.compile(r'\[([^\]]+)\]\(([^)\s]+)\)')
_CODE = re.compile(r'`([^`]+)`')


def format_note(text: str) -> Markup:
    """Escape, then turn [text](http...) into a link (other targets keep only the text) and `code` into <code>."""
    def link(match):
        target = match.group(2)
        if target.startswith(('http://', 'https://')):
            return f'<a href="{target}" target="_blank" rel="noopener noreferrer">{match.group(1)}</a>'
        return match.group(1)
    return Markup(_CODE.sub(r'<code>\1</code>', _LINK.sub(link, str(escape(text)))))


def _short(text: str) -> str:
    return text if len(text) <= LABEL_CHARS else text[:LABEL_CHARS - 1].rstrip() + '…'


def _lane_of(section: Section) -> int:
    return 0 if section.official else (2 if section.suggested else 1)


def build_timeline(sections: List[Section], today: datetime.date) -> Optional[Dict]:
    """SVG geometry (viewBox units) of the three-lane timeline, or None when no row has a date."""
    dated = [(s, r) for s in sections for r in s.rows if r.start is not None]
    if not dated:
        return None
    first = min(r.start for _, r in dated) - datetime.timedelta(days=PAD_DAYS)
    last = max(r.end for _, r in dated) + datetime.timedelta(days=PAD_DAYS)
    span = (last - first).days
    right = WIDTH - RIGHT

    def x_of(date: datetime.date) -> float:
        return round(LEFT + (date - first).days / span * (right - LEFT), 1)

    items: List[Dict] = []
    for section, row in dated:
        x0, x1 = x_of(row.start), x_of(row.end)
        is_range = row.start != row.end
        width = len(_short(row.task)) * CHAR_WIDTH
        # The label goes right of the item, or left of it when it would run past the card.
        label_left = x1 + 10 + width > right
        label_x = x0 - 10 if label_left else x1 + 10
        extent = (label_x - width, x1 + 6) if label_left else (x0 - 6, label_x + width)
        items.append({
            'lane': _lane_of(section), 'kind': 'bar' if is_range else 'dot', 'x': x0, 'x1': max(x1, x0 + 4),
            'label': _short(row.task), 'label_x': round(label_x, 1), 'anchor': 'end' if label_left else 'start',
            'extent': extent, 'status': row.status, 'suggested': section.suggested,
            'due': row.end.isoformat(), 'overdue': is_overdue(row, today),
            'tip': f"{row.task} · {due_label(row)} · {thesis.GUIDE_STATUS_LABELS[row.status]}"
                   + (' · đề xuất' if section.suggested else ''),
            'countdown': countdown_text(row, today)})

    lanes = []
    y = HEADER
    for index, name in enumerate(thesis.GUIDE_LANE_LABELS):
        mine = sorted((i for i in items if i['lane'] == index), key=lambda i: i['extent'][0])
        ends: List[float] = []
        for item in mine:
            slot = next((n for n, end in enumerate(ends) if item['extent'][0] > end + 6), len(ends))
            if slot == len(ends):
                ends.append(0.0)
            ends[slot] = item['extent'][1]
            item['y'] = y + 14 + slot * SUBROW
        height = max(len(ends), 1) * SUBROW + 10
        lanes.append({'name': name, 'y': y, 'height': height, 'suggested': index == 2})
        y += height + LANE_GAP

    ticks = []
    month = datetime.date(first.year, first.month, 1)
    while month <= last:
        if month >= first:
            ticks.append({'x': x_of(month), 'label': f'T{month.month}/{month.year}'})
        month = datetime.date(month.year + (month.month == 12), month.month % 12 + 1, 1)
    return {'width': WIDTH, 'height': y, 'x0': LEFT, 'x1': right, 'start': first.isoformat(), 'end': last.isoformat(),
            'ticks': ticks, 'lanes': lanes, 'items': items, 'today_x': x_of(today) if first <= today <= last else None}


def js_rows(sections: List[Section]) -> List[Dict]:
    """The official rows as the browser script needs them to recompute the headline for its own today."""
    if not sections:
        return []
    return [{'task': r.task, 'start': r.start.isoformat() if r.start else None, 'end': r.end.isoformat() if r.end else None,
             'status': r.status} for r in sections[0].rows]


def build_view(directory: str, today_fn: Callable[[], datetime.date]) -> Dict:
    """Everything the guide page shows; missing files give None / empty parts, never an error."""
    today = today_fn()
    checklist = read_text(directory, CHECKLIST_FILE)
    sections, problems = parse_checklist(checklist) if checklist is not None else ([], [])
    rows = [r for s in sections for r in s.rows]
    nxt, submit = next_official(sections, today), submission_row(sections)
    return {
        'today': today, 'today_text': format_date(today), 'checklist_ready': checklist is not None,
        'guide': read_text(directory, GUIDE_FILE), 'sections': sections, 'warnings': all_warnings(sections, problems),
        'timeline': build_timeline(sections, today), 'counts': status_counts(sections),
        'overdue': sum(is_overdue(r, today) for r in rows), 'next': nxt, 'submission': submit,
        'next_left': days_left(nxt, today) if nxt else None,
        'submission_left': days_left(submit, today) if submit else None,
        'official_rows': js_rows(sections), 'submission_date': thesis.THESIS_SUBMISSION_DATE}
