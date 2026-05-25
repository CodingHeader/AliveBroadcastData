import re
from datetime import datetime

def parse_number(text: str):
    if not text or text == "--":
        return None
    text = text.strip()
    if "万" in text:
        return int(float(text.replace("万", "")) * 10000)
    if "%" in text:
        return text
    text = text.replace(",", "")
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text

def parse_time(text: str) -> str:
    if re.match(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", text):
        return text
    text = text.replace("：", ":")
    now = datetime.now()
    match = re.match(r"(\d{2})-(\d{2})\s+(\d{2}):(\d{2})(?::(\d{2}))?", text)
    if match:
        month, day, hour, minute = int(match.group(1)), int(match.group(2)), int(match.group(3)), int(match.group(4))
        second = int(match.group(5)) if match.group(5) else 0
        year = now.year if month <= now.month else now.year - 1
        return f"{year}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}"
    return text

def format_duration(minutes: int) -> str:
    h, m = divmod(minutes, 60)
    if h > 0:
        return f"{h}小时{m}分钟"
    return f"{m}分钟"

def format_duration_hms(start_time: str, end_time: str) -> str:
    """从起止时间计算精确时长，返回 H:MM:SS 格式"""
    try:
        start_dt = datetime.strptime(start_time, "%Y-%m-%d %H:%M:%S")
        end_dt = datetime.strptime(end_time, "%Y-%m-%d %H:%M:%S")
        total_seconds = int((end_dt - start_dt).total_seconds())
        if total_seconds < 0:
            return "—"
        h, remainder = divmod(total_seconds, 3600)
        m, s = divmod(remainder, 60)
        return f"{h}:{m:02d}:{s:02d}"
    except (ValueError, TypeError):
        return "—"
