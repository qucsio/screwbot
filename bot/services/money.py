"""Разбор денежных сумм, введённых руками."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# Предел колонок Numeric(12, 2) в БД.
MONEY_MAX = Decimal("9999999999.99")


def parse_money(text: str | None, allow_zero: bool = False) -> Decimal | None:
    """Сумма из «1500», «1 500», «1500,50», «1500₽» или None.

    None и для всего, что Decimal проглотил бы молча: NaN, Infinity,
    отрицательные числа и суммы, не влезающие в колонку БД.
    """
    if not text:
        return None
    cleaned = "".join(text.replace(",", ".").replace("₽", "").split())
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or amount > MONEY_MAX:
        return None
    amount = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if amount == 0 and not allow_zero:
        return None
    return amount


def fmt_money(value) -> str:
    """Сумма для показа: 5000 → «5 000», 1500.5 → «1 500.50», None → «—»."""
    if value is None:
        return "—"
    amount = Decimal(str(value))
    if not amount.is_finite():  # записи, сохранённые до проверки NaN
        return "—"
    text = f"{amount.quantize(Decimal('0.01')):,.2f}".replace(",", " ")
    return text[:-3] if text.endswith(".00") else text
