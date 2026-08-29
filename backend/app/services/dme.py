"""
Motor de cálculo del % DME (Disponibilidad de Medicamentos Esenciales).

    DME = (normostock + sobrestock) / (desabastecido + critico + substock
          + normostock + sobrestock) × 100

Se calcula solo sobre productos del petitorio (producto.es_petitorio) y
sobre `situacion_eess` (dispo = stock_aem / cpma, SIN el almacén central
— ver app/repositories/dme_repository.py). "Sin rotación" se excluye del
todo (no se puede evaluar disponibilidad de algo sin consumo histórico).
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

SITUACIONES_DISPONIBLES = ("NORMOSTOCK", "SOBRESTOCK")
SITUACIONES_EVALUABLES = ("DESABASTECIDO", "CRITICO", "SUBSTOCK", "NORMOSTOCK", "SOBRESTOCK")


@dataclass
class ResultadoDME:
    total_evaluados: int
    total_disponibles: int
    porcentaje: Decimal
    semaforo: str


def clasificar_semaforo(porcentaje: Decimal) -> str:
    if porcentaje > 90:
        return "VERDE_OSCURO"
    if porcentaje >= 80:
        return "VERDE"
    if porcentaje >= 70:
        return "AMARILLO"
    return "ROJO"


def calcular_dme(situaciones_eess: list[str]) -> ResultadoDME | None:
    """
    situaciones_eess: una `situacion_eess` por cada producto del petitorio
    evaluado (de calc_cpma, ya filtrado por es_petitorio). Devuelve None
    si no hay nada evaluable (todo "sin rotación" o lista vacía) — no se
    fuerza un 0% que sugeriría desabastecimiento total sin serlo.
    """
    evaluables = [s for s in situaciones_eess if s in SITUACIONES_EVALUABLES]
    total_evaluados = len(evaluables)
    if total_evaluados == 0:
        return None

    total_disponibles = sum(1 for s in evaluables if s in SITUACIONES_DISPONIBLES)
    porcentaje = Decimal(total_disponibles * 100) / total_evaluados
    porcentaje = porcentaje.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return ResultadoDME(
        total_evaluados=total_evaluados,
        total_disponibles=total_disponibles,
        porcentaje=porcentaje,
        semaforo=clasificar_semaforo(porcentaje),
    )
