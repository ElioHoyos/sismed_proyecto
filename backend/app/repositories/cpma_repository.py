"""Recalcula calc_cpma/calc_cpma_red con el motor de app/services/cpma.py."""
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.calc_cpma import CalcCpma
from app.models.calc_cpma_red import CalcCpmaRed
from app.models.ici import Ici
from app.models.stock_almacen import ORIGEN_ALMACEN, Stock
from app.services.cpma import evaluar_producto

_COLUMNAS_ACTUALIZABLES = tuple(
    c.name for c in CalcCpma.__table__.columns
    if c.name not in ("establecimiento_id", "producto_id", "periodo")
)
_COLUMNAS_ACTUALIZABLES_RED = tuple(
    c.name for c in CalcCpmaRed.__table__.columns
    if c.name not in ("producto_id", "periodo")
)


def _restar_meses(anio: int, mes: int, n: int) -> tuple[int, int]:
    total = anio * 12 + (mes - 1) - n
    return total // 12, total % 12 + 1


def recalcular_cpma(db: Session, pares: set[tuple[int, int]]) -> int:
    """Ventana fija de 12 meses calendario terminando en el periodo más
    reciente de cada par (establecimiento_id, producto_id) — no "los
    últimos 12 registros", para no correr la ventana si hay meses sin importar."""
    if not pares:
        return 0

    filas_upsert = []
    for establecimiento_id, producto_id in pares:
        ultimo = db.execute(
            select(Ici.anio, Ici.mes, Ici.stock_final)
            .where(Ici.establecimiento_id == establecimiento_id, Ici.producto_id == producto_id)
            .order_by(Ici.anio.desc(), Ici.mes.desc())
            .limit(1)
        ).first()
        if ultimo is None:
            continue
        # stock_final del ICI = stock de la RED de este establecimiento (stock_red).
        anio_fin, mes_fin, stock_red = ultimo

        anio_ini, mes_ini = _restar_meses(anio_fin, mes_fin, 11)
        yyyymm_ini = anio_ini * 100 + mes_ini
        yyyymm_fin = anio_fin * 100 + mes_fin

        consumos = db.scalars(
            select(Ici.consumo).where(
                Ici.establecimiento_id == establecimiento_id,
                Ici.producto_id == producto_id,
                (Ici.anio * 100 + Ici.mes).between(yyyymm_ini, yyyymm_fin),
            )
        ).all()

        # El almacén central es el AEM (Almacén Especializado de Medicamentos).
        stock_aem = db.scalar(
            select(func.coalesce(func.sum(Stock.cantidad), 0))
            .where(Stock.origen == ORIGEN_ALMACEN, Stock.producto_id == producto_id)
        )

        resultado = evaluar_producto(
            [Decimal(c) for c in consumos],
            stock_red=Decimal(stock_red or 0),
            stock_aem=Decimal(stock_aem or 0),
        )

        filas_upsert.append({
            "establecimiento_id": establecimiento_id,
            "producto_id": producto_id,
            "periodo": date(anio_fin, mes_fin, 1),
            "sumames": resultado.sumames,
            "contador": resultado.contador,
            "cpma": resultado.cpma,
            "stock_red": resultado.stock_red,
            "stock_aem": resultado.stock_aem,
            "dispo": resultado.dispo,
            "dispo_total": resultado.dispo_total,
            "situacion": resultado.situacion,
            "situacion_total": resultado.situacion_total,
        })

    if not filas_upsert:
        return 0

    _guardar_calc_cpma(db, filas_upsert)
    return len(filas_upsert)


def _guardar_calc_cpma(db: Session, filas_upsert: list[dict]) -> None:
    stmt = mysql_insert(CalcCpma).values(filas_upsert)
    actualizables = {col: stmt.inserted[col] for col in _COLUMNAS_ACTUALIZABLES}
    stmt = stmt.on_duplicate_key_update(**actualizables)
    db.execute(stmt)


def recalcular_cpma_red(db: Session, producto_ids: set[int]) -> int:
    """Consumo mensual sumado entre TODOS los establecimientos antes de
    aplicar SUMAMES/CONTADOR — no es el promedio de los CPMA individuales."""
    if not producto_ids:
        return 0

    filas_upsert = []
    for producto_id in producto_ids:
        ultimo = db.execute(
            select(func.max(Ici.anio * 100 + Ici.mes)).where(Ici.producto_id == producto_id)
        ).scalar()
        if ultimo is None:
            continue
        anio_fin, mes_fin = divmod(ultimo, 100)

        anio_ini, mes_ini = _restar_meses(anio_fin, mes_fin, 11)
        yyyymm_ini = anio_ini * 100 + mes_ini

        consumos_mensuales = db.execute(
            select(func.sum(Ici.consumo))
            .where(
                Ici.producto_id == producto_id,
                (Ici.anio * 100 + Ici.mes).between(yyyymm_ini, ultimo),
            )
            .group_by(Ici.anio, Ici.mes)
        ).scalars().all()

        # stock de la RED = suma del stock_final de todos los establecimientos.
        stock_red = db.scalar(
            select(func.coalesce(func.sum(Ici.stock_final), 0)).where(
                Ici.producto_id == producto_id, Ici.anio == anio_fin, Ici.mes == mes_fin
            )
        )
        # AEM = almacén central.
        stock_aem = db.scalar(
            select(func.coalesce(func.sum(Stock.cantidad), 0))
            .where(Stock.origen == ORIGEN_ALMACEN, Stock.producto_id == producto_id)
        )

        resultado = evaluar_producto(
            [Decimal(c) for c in consumos_mensuales],
            stock_red=Decimal(stock_red or 0),
            stock_aem=Decimal(stock_aem or 0),
        )

        filas_upsert.append({
            "producto_id": producto_id,
            "periodo": date(anio_fin, mes_fin, 1),
            "sumames": resultado.sumames,
            "contador": resultado.contador,
            "cpma": resultado.cpma,
            "stock_red": resultado.stock_red,
            "stock_aem": resultado.stock_aem,
            "dispo": resultado.dispo,
            "dispo_total": resultado.dispo_total,
            "situacion": resultado.situacion,
            "situacion_total": resultado.situacion_total,
        })

    if not filas_upsert:
        return 0

    _guardar_calc_cpma_red(db, filas_upsert)
    return len(filas_upsert)


def _guardar_calc_cpma_red(db: Session, filas_upsert: list[dict]) -> None:
    stmt = mysql_insert(CalcCpmaRed).values(filas_upsert)
    actualizables = {col: stmt.inserted[col] for col in _COLUMNAS_ACTUALIZABLES_RED}
    stmt = stmt.on_duplicate_key_update(**actualizables)
    db.execute(stmt)


def recalcular_por_productos(db: Session, producto_ids: set[int]) -> tuple[int, int]:
    """Para cambios que afectan solo STOCK (no consumo): usa los pares
    (establecimiento, producto) que ya existen en calc_cpma en vez de descubrir nuevos."""
    if not producto_ids:
        return 0, 0

    pares = set(
        db.execute(
            select(CalcCpma.establecimiento_id, CalcCpma.producto_id).where(
                CalcCpma.producto_id.in_(producto_ids)
            )
        ).all()
    )
    n_est = recalcular_cpma(db, pares)
    n_red = recalcular_cpma_red(db, producto_ids)
    return n_est, n_red
