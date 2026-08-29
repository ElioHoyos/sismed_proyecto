"""
Motor de cálculo CPMA (Consumo Promedio Mensual Ajustado).

    SUMAMES  = suma del consumo de los últimos 12 meses
    CONTADOR = nº de meses (de esos 12) con consumo > 0
    CPMA     = SUMAMES / CONTADOR        ← NO se divide entre 12

El ajuste está en el denominador: se divide entre los meses que
efectivamente tuvieron consumo, para no subestimar productos
desabastecidos o de rotación estacional.
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

VENTANA_MESES = 12
MESES_A_CUBRIR_DEFAULT = 3


@dataclass
class ResultadoCPMA:
    sumames: Decimal
    contador: int
    cpma: Decimal
    # stock_red = stock de la Red (establecimientos); stock_aem = Almacén
    # Especializado de Medicamentos (almacén central). Ver la nota de la
    # inversión en app/repositories/cpma_repository.py.
    stock_red: Decimal
    stock_aem: Decimal
    dispo: Decimal  # stock_red / cpma  → SITUACION (vista EESS)
    dispo_total: Decimal  # (stock_red + stock_aem) / cpma → SITUACION_TOTAL (Red+AEM)
    situacion: str
    situacion_total: str


def _redondear(valor: Decimal, decimales: str = "0.01") -> Decimal:
    return Decimal(valor).quantize(Decimal(decimales), rounding=ROUND_HALF_UP)


def calcular_cpma(consumos_12m: list[Decimal]) -> tuple[Decimal, int, Decimal]:
    """Ej.: 671 repartido en 4 de 12 meses → CPMA = 671/4 = 167.75, no 671/12."""
    sumames = sum((Decimal(c) for c in consumos_12m), Decimal(0))
    contador = sum(1 for c in consumos_12m if Decimal(c) > 0)

    if contador == 0:
        return sumames, 0, Decimal(0)

    cpma = _redondear(sumames / contador)
    return sumames, contador, cpma


def clasificar_situacion(dispo: Decimal, cpma: Decimal) -> str:
    if cpma == 0:
        return "SIN ROTACION"
    if dispo == 0:
        return "DESABASTECIDO"
    if dispo < 1:
        return "CRITICO"
    if dispo <= 2:
        return "SUBSTOCK"
    if dispo <= 6:
        return "NORMOSTOCK"
    return "SOBRESTOCK"


def evaluar_producto(
    consumos_12m: list[Decimal],
    stock_red: Decimal,
    stock_aem: Decimal = Decimal(0),
) -> ResultadoCPMA:
    """DISPO = stock_red / CPMA (cobertura del EESS/Red).
    DISPO_TOTAL = (stock_red + stock_aem) / CPMA (Red + almacén AEM)."""
    sumames, contador, cpma = calcular_cpma(consumos_12m)

    stock_red = Decimal(stock_red)
    stock_aem = Decimal(stock_aem)

    if cpma > 0:
        dispo = _redondear(stock_red / cpma)
        dispo_total = _redondear((stock_red + stock_aem) / cpma)
    else:
        dispo = Decimal(0)
        dispo_total = Decimal(0)

    return ResultadoCPMA(
        sumames=sumames,
        contador=contador,
        cpma=cpma,
        stock_red=stock_red,
        stock_aem=stock_aem,
        dispo=dispo,
        dispo_total=dispo_total,
        situacion=clasificar_situacion(dispo, cpma),
        situacion_total=clasificar_situacion(dispo_total, cpma),
    )


def requisicion_sugerida(
    cpma: Decimal,
    stock_disponible: Decimal,
    meses_a_cubrir: int = MESES_A_CUBRIR_DEFAULT,
) -> Decimal:
    """cantidad = CPMA × meses_a_cubrir − stock_disponible, nunca negativo."""
    necesidad = Decimal(cpma) * meses_a_cubrir - Decimal(stock_disponible)
    return max(Decimal(0), _redondear(necesidad, "1"))
