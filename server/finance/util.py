"""Dates: everything is stored as ISO text ('2026-11-08') and months as 'YYYY-MM'."""
import calendar
from datetime import date


def today(): return date.today()
def iso(d): return d.isoformat()
def parse_date(s): return date.fromisoformat(s) if isinstance(s, str) else s
def ym(d): d = parse_date(d); return f'{d.year:04d}-{d.month:02d}'
def this_month(): return ym(today())


def add_months(m, n):
    """'2026-11' + 3 → '2027-02'"""
    y, mo = int(m[:4]), int(m[5:7]); t = y * 12 + (mo - 1) + n
    return f'{t // 12:04d}-{t % 12 + 1:02d}'


def clip_day(m, day):
    y, mo = int(m[:4]), int(m[5:7]); return date(y, mo, max(1, min(int(day), calendar.monthrange(y, mo)[1])))


def month_bounds(m):
    y, mo = int(m[:4]), int(m[5:7]); return date(y, mo, 1), date(y, mo, calendar.monthrange(y, mo)[1])


def add_months_date(d, n):
    d = parse_date(d); m = add_months(ym(d), n); return clip_day(m, d.day)


def full_months_between(d1, d2):
    """completed months from d1 to d2 (Mar 3 → Nov 8 = 8; Mar 3 → Nov 2 = 7)"""
    d1, d2 = parse_date(d1), parse_date(d2)
    n = (d2.year - d1.year) * 12 + (d2.month - d1.month)
    return n - 1 if d2.day < d1.day and not (d2.day == calendar.monthrange(d2.year, d2.month)[1] and d1.day > d2.day) else n


def month_label(m):
    y, mo = int(m[:4]), int(m[5:7]); return f'{calendar.month_name[mo]} {y}'


def short_month(m): return calendar.month_abbr[int(m[5:7])]


def month_diff(a, b):
    """whole months from month a to month b ('YYYY-MM')"""
    return (int(b[:4]) - int(a[:4])) * 12 + (int(b[5:7]) - int(a[5:7]))
