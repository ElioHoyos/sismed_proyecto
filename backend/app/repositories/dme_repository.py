"""Recalcula y lee calc_dme/calc_dme_red — ver app/services/dme.py (motor)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.calc_cpma import CalcCpma
from app.models.calc_dme import CalcDme, CalcDmeRed
from app.models.establecimiento import Establecimiento
from app.models.producto import Producto
from app.services.dme import calcular_dme

_COLUMNAS_ACTUALIZABLES = tuple(
    c.name for c in CalcDme.__table__.columns
    if c.name not in ("establecimiento_id", "periodo")
)
_COLUMNAS_ACTUALIZABLES_RED = tuple(
    c.name for c in CalcDmeRed.__table__.columns if c.name != "periodo"
)


# El DME se evalúa sobre el universo del doc: Soporte (S) + SIS (_), excluyendo
# los Estratégicos (E). Usa la SITUACION corregida (stock_red / cpma), no la vieja
# situacion_eess (eliminada tras corregir la inversión stock/stock_aem).
_MEDEST_EVALUABLES = ("S", "_")


def _situaciones_evaluables(db: Session, establecimiento_id: int, periodo: date) -> list[str]:
    return list(
        db.scalars(
            select(CalcCpma.situacion)
            .join(Producto, Producto.id == CalcCpma.producto_id)
            .where(
                CalcCpma.establecimiento_id == establecimiento_id,
                CalcCpma.periodo == periodo,
                Producto.medest.in_(_MEDEST_EVALUABLES),
            )
        ).all()
    )


def recalcular_dme(db: Session, establecimiento_ids: set[int]) -> tuple[int, int]:
    """
    Para cada establecimiento: toma su periodo más reciente en calc_cpma
    y cuenta situacion_eess de sus productos del petitorio. Si no hay
    nada evaluable (todo "sin rotación" o sin productos del petitorio
    con datos), no se crea fila — un 0% falso sugeriría desabastecimiento
    total sin serlo.

    También recalcula calc_dme_red: mismo conteo pero sobre TODOS los
    establecimientos que compartan el periodo más reciente global.

    Devuelve (establecimientos recalculados, 1 si se recalculó la red
    (0 si no había nada evaluable en la red)).
    """
    filas_dme = []
    for establecimiento_id in establecimiento_ids:
        periodo = db.scalar(
            select(func.max(CalcCpma.periodo)).where(CalcCpma.establecimiento_id == establecimiento_id)
        )
        if periodo is None:
            continue

        situaciones = _situaciones_evaluables(db, establecimiento_id, periodo)
        resultado = calcular_dme(situaciones)
        if resultado is None:
            continue

        filas_dme.append({
            "establecimiento_id": establecimiento_id,
            "periodo": periodo,
            "total_evaluados": resultado.total_evaluados,
            "total_disponibles": resultado.total_disponibles,
            "porcentaje": resultado.porcentaje,
            "semaforo": resultado.semaforo,
        })

    if filas_dme:
        _guardar_calc_dme(db, filas_dme)

    n_red = _recalcular_dme_red(db)
    return len(filas_dme), n_red


def _recalcular_dme_red(db: Session) -> int:
    periodo = db.scalar(select(func.max(CalcCpma.periodo)))
    if periodo is None:
        return 0

    situaciones = list(
        db.scalars(
            select(CalcCpma.situacion)
            .join(Producto, Producto.id == CalcCpma.producto_id)
            .where(CalcCpma.periodo == periodo, Producto.medest.in_(_MEDEST_EVALUABLES))
        ).all()
    )
    resultado = calcular_dme(situaciones)
    if resultado is None:
        return 0

    stmt = mysql_insert(CalcDmeRed).values([{
        "periodo": periodo,
        "total_evaluados": resultado.total_evaluados,
        "total_disponibles": resultado.total_disponibles,
        "porcentaje": resultado.porcentaje,
        "semaforo": resultado.semaforo,
    }])
    actualizables = {col: stmt.inserted[col] for col in _COLUMNAS_ACTUALIZABLES_RED}
    db.execute(stmt.on_duplicate_key_update(**actualizables))
    return 1


def _guardar_calc_dme(db: Session, filas: list[dict]) -> None:
    stmt = mysql_insert(CalcDme).values(filas)
    actualizables = {col: stmt.inserted[col] for col in _COLUMNAS_ACTUALIZABLES}
    db.execute(stmt.on_duplicate_key_update(**actualizables))


def listar_dme(db: Session, periodo: date | None = None) -> tuple[date | None, list[dict]]:
    periodo_usado = periodo or db.scalar(select(func.max(CalcDme.periodo)))
    if periodo_usado is None:
        return None, []

    filas = db.execute(
        select(CalcDme, Establecimiento)
        .join(Establecimiento, Establecimiento.id == CalcDme.establecimiento_id)
        .where(CalcDme.periodo == periodo_usado)
        .order_by(Establecimiento.nombre)
    ).all()

    return periodo_usado, [
        {
            "establecimiento_cod": est.cod_2000,
            "establecimiento_nombre": est.nombre,
            "total_evaluados": d.total_evaluados,
            "total_disponibles": d.total_disponibles,
            "porcentaje": d.porcentaje,
            "semaforo": d.semaforo,
        }
        for d, est in filas
    ]


def obtener_dme_red(db: Session, periodo: date | None = None) -> dict | None:
    periodo_usado = periodo or db.scalar(select(func.max(CalcDmeRed.periodo)))
    if periodo_usado is None:
        return None

    fila = db.scalar(select(CalcDmeRed).where(CalcDmeRed.periodo == periodo_usado))
    if fila is None:
        return None

    return {
        "periodo": periodo_usado,
        "total_evaluados": fila.total_evaluados,
        "total_disponibles": fila.total_disponibles,
        "porcentaje": fila.porcentaje,
        "semaforo": fila.semaforo,
    }
