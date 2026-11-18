"""Money is kept as whole minor units (paisa / cents) in the database so sums never drift."""
import re
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation

SYMBOL = {'PKR': 'Rs', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹', 'AED': 'AED', 'SAR': 'SAR', 'CAD': 'C$', 'AUD': 'A$', 'JPY': '¥'}
PLAIN = {'PKR', 'INR', 'JPY'}                      # shown without decimals unless there are some


def to_minor(x):
    if x is None or x == '': return 0
    if isinstance(x, int): return x * 100
    try: d = Decimal(str(x).replace(',', '').replace(' ', ''))
    except InvalidOperation: raise ValueError(f'not a number: {x!r}')
    return int((d * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))


def parse_amount(text):
    """'12,500' → 1250000 · '1 250.50' → 125050 · accepts Arabic-Indic digits too"""
    t = (text or '').strip()
    t = t.translate(str.maketrans('٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹', '01234567890123456789')).replace('٫', '.').replace('٬', ',')
    t = re.sub(r'[^\d.,\-]', '', t)
    if not t or t in '-.': raise ValueError('Enter an amount')
    return to_minor(t)


def fmt(m, cur=None, sign=False, symbol=True, whole=False):
    """12500000 → 'Rs 125,000' · 125050,'USD' → '$1,250.50' · whole=True rounds PKR-like totals to whole rupees"""
    if m is None: return '—'
    neg = m < 0; a = abs(int(m))
    if whole and cur in PLAIN: a = int((a + 50) // 100) * 100
    whole_part, cents = divmod(a, 100)
    if cur in PLAIN and cents == 0: body = f'{whole_part:,}'
    else: body = f'{whole_part:,}.{cents:02d}'
    pre = (SYMBOL.get(cur, cur) if cur else '') if symbol else ''
    sp = ' ' if pre and (len(pre) > 1) else ''
    s = f'{pre}{sp}{body}'
    if neg: s = '−' + s
    elif sign and m > 0: s = '+' + s
    return s


def fmt_plain(m):
    """for input boxes: no symbol, no thousands separators"""
    whole, cents = divmod(abs(int(m)), 100)
    return (('-' if m < 0 else '') + (f'{whole}' if cents == 0 else f'{whole}.{cents:02d}'))
