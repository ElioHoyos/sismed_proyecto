"""Conversión de campos numéricos de SISMED (compartida entre importadores)."""
from decimal import Decimal, InvalidOperation


def a_decimal(valor) -> Decimal | None:
    """None → 0, vacío/espacios → 0 (así representa FoxPro "sin
    movimiento"), no numérico → None (incidencia, nunca cero silencioso)."""
    if valor is None:
        return Decimal(0)
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, int):
        return Decimal(valor)
    if isinstance(valor, float):
        return Decimal(str(valor))
    texto = str(valor).strip()
    if texto == "":
        return Decimal(0)
    try:
        return Decimal(texto)
    except InvalidOperation:
        return None
