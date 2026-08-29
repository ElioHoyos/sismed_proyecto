"""Historial de correcciones de stock (negativos por lote): motor de comparación
entre cargas + consultas de la línea de tiempo.

El corazón: `actualizar_historial_negativos` compara la foto nueva contra las
incidencias abiertas del mismo lugar y detecta SOLO (sin depender del check
humano) qué negativos siguen, cuáles se resolvieron y cuáles son nuevos."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import and_, desc, func, select
from sqlalchemy.orm import Session

from app.models.establecimiento import Establecimiento
from app.models.incidencia_stock import (
    ESTADO_PENDIENTE,
    ESTADO_RESUELTO,
    TIPO_NEGATIVO,
    IncidenciaStock,
    RevisionStock,
)
from app.models.producto import Producto
from app.models.stock_almacen import ORIGEN_ALMACEN, ORIGEN_EESS_LOTE, Stock


def _cond_ubicacion(origen: str, almacen_cod: str | None, establecimiento_id: int | None):
    if origen == ORIGEN_ALMACEN:
        return and_(IncidenciaStock.origen == origen, IncidenciaStock.almacen_cod == almacen_cod)
    return and_(IncidenciaStock.origen == origen, IncidenciaStock.establecimiento_id == establecimiento_id)


def actualizar_historial_negativos(
    db: Session,
    *,
    origen: str,
    almacen_cod: str | None,
    establecimiento_id: int | None,
    filas_nuevas: list[dict],
    medcod_por_id: dict[int, str],
    importacion_id: int | None,
    ahora: datetime,
) -> None:
    """Compara la foto nueva de una ubicación contra sus incidencias de negativo
    abiertas: resuelve las que ya no aparecen, actualiza las que siguen y abre
    las nuevas. Idempotente: reimportar la misma foto no duplica ni resuelve de
    más (se emparejan por producto + lote). No hace commit (lo hace el importador)."""
    # Valor actual por (producto, lote) en esta ubicación (consolida fecha-split).
    actual: dict[tuple[int, str], Decimal] = {}
    for f in filas_nuevas:
        clave = (f["producto_id"], f["lote"])
        actual[clave] = actual.get(clave, Decimal(0)) + Decimal(str(f["cantidad"]))
    negativos = {k: v for k, v in actual.items() if v < 0}

    abiertas = db.scalars(
        select(IncidenciaStock).where(
            IncidenciaStock.tipo == TIPO_NEGATIVO,
            IncidenciaStock.estado == ESTADO_PENDIENTE,
            _cond_ubicacion(origen, almacen_cod, establecimiento_id),
        )
    ).all()
    abiertas_por_clave = {(i.producto_id, i.lote): i for i in abiertas}

    # Incidencias abiertas: siguen (actualizar) o se resolvieron (marcar).
    for clave, inc in abiertas_por_clave.items():
        if clave in negativos:
            inc.valor_actual = negativos[clave]
            inc.ultima_carga_en = ahora
        else:
            inc.estado = ESTADO_RESUELTO
            inc.resuelto_en = ahora
            inc.resuelto_importacion_id = importacion_id
            # Valor nuevo: positivo si sigue en stock, 0 si el lote salió del stock.
            inc.valor_resuelto = actual.get(clave, Decimal(0))

    # Negativos nuevos (no había incidencia abierta): se registran como detectados.
    for clave, val in negativos.items():
        if clave in abiertas_por_clave:
            continue
        prod_id, lote = clave
        db.add(
            IncidenciaStock(
                tipo=TIPO_NEGATIVO,
                origen=origen,
                almacen_cod=almacen_cod,
                establecimiento_id=establecimiento_id,
                producto_id=prod_id,
                medcod=medcod_por_id.get(prod_id, ""),
                lote=lote,
                detectado_en=ahora,
                detectado_importacion_id=importacion_id,
                valor_detectado=val,
                valor_actual=val,
                ultima_carga_en=ahora,
                estado=ESTADO_PENDIENTE,
            )
        )


def sembrar_historial_desde_stock(db: Session, ahora: datetime | None = None) -> int:
    """Backfill: los negativos que YA existían antes del motor (nunca se vio su
    'aparición') no están en el historial. Recorre el stock negativo actual
    (almacén y EESS) y crea una incidencia PENDIENTE para cada lote negativo que
    no tenga ya una abierta, con la fecha actual como detección (marcada como
    inicial, para ser honestos con el dato). Idempotente: no duplica."""
    ahora = ahora or datetime.now()
    # Negativos actuales por (ubicación, producto, lote), sumando fecha-splits.
    grupos = db.execute(
        select(
            Stock.origen,
            Stock.almacen_cod,
            Stock.establecimiento_id,
            Stock.producto_id,
            Producto.medcod,
            Stock.lote,
            func.sum(Stock.cantidad).label("saldo"),
        )
        .join(Producto, Producto.id == Stock.producto_id)
        .where(Stock.origen.in_((ORIGEN_ALMACEN, ORIGEN_EESS_LOTE)), Stock.lote.isnot(None))
        .group_by(Stock.origen, Stock.almacen_cod, Stock.establecimiento_id, Stock.producto_id, Producto.medcod, Stock.lote)
        .having(func.sum(Stock.cantidad) < 0)
    ).all()

    creadas = 0
    for origen, almacen_cod, est_id, prod_id, medcod, lote, saldo in grupos:
        existe = db.scalar(
            select(IncidenciaStock.id).where(
                IncidenciaStock.tipo == TIPO_NEGATIVO,
                IncidenciaStock.estado == ESTADO_PENDIENTE,
                _cond_ubicacion(origen, almacen_cod, est_id),
                IncidenciaStock.producto_id == prod_id,
                IncidenciaStock.lote == lote,
            ).limit(1)
        )
        if existe:
            continue
        db.add(
            IncidenciaStock(
                tipo=TIPO_NEGATIVO,
                origen=origen,
                almacen_cod=almacen_cod,
                establecimiento_id=est_id,
                producto_id=prod_id,
                medcod=medcod,
                lote=lote,
                detectado_en=ahora,
                detectado_importacion_id=None,
                detectado_inicial=True,
                valor_detectado=saldo,
                valor_actual=saldo,
                ultima_carga_en=ahora,
                estado=ESTADO_PENDIENTE,
            )
        )
        creadas += 1
    if creadas:
        db.commit()
    return creadas


def mapa_incidencias_abiertas(
    db: Session, origen: str, establecimiento_cod: str | None = None
) -> dict[tuple[int, str], dict]:
    """Para el Stock: (producto_id, lote) → {incidencia_id, revisado} de las
    incidencias de negativo ABIERTAS, para poder marcar el check desde ahí."""
    stmt = (
        select(IncidenciaStock, RevisionStock)
        .outerjoin(RevisionStock, RevisionStock.incidencia_id == IncidenciaStock.id)
        .where(IncidenciaStock.tipo == TIPO_NEGATIVO, IncidenciaStock.estado == ESTADO_PENDIENTE, IncidenciaStock.origen == origen)
    )
    if establecimiento_cod:
        stmt = stmt.join(Establecimiento, Establecimiento.id == IncidenciaStock.establecimiento_id).where(
            Establecimiento.cod_2000 == establecimiento_cod
        )
    salida: dict[tuple[int, str], dict] = {}
    for inc, rev in db.execute(stmt).all():
        salida[(inc.producto_id, inc.lote)] = {
            "incidencia_id": inc.id,
            "revisado": rev is not None,
            "revisado_en": rev.revisado_en.isoformat() if rev and rev.revisado_en else None,
            "nota": rev.nota if rev else None,
        }
    return salida


# ── Consultas de la vista de historial ─────────────────────────────────────

def _mes_rango(mes: str) -> tuple[date, date]:
    anio, m = (int(x) for x in mes.split("-"))
    ini = date(anio, m, 1)
    fin = date(anio + (m == 12), (m % 12) + 1, 1)
    return ini, fin


def listar_historial(
    db: Session,
    estado: str = "todos",  # pendientes | resueltos | todos
    origen: str | None = None,
    establecimiento_cod: str | None = None,
    mes: str | None = None,
) -> list[dict]:
    stmt = (
        select(IncidenciaStock, Producto, Establecimiento, RevisionStock)
        .join(Producto, Producto.id == IncidenciaStock.producto_id)
        .outerjoin(Establecimiento, Establecimiento.id == IncidenciaStock.establecimiento_id)
        .outerjoin(RevisionStock, RevisionStock.incidencia_id == IncidenciaStock.id)
        .order_by(desc(IncidenciaStock.detectado_en))
    )
    if estado == "pendientes":
        stmt = stmt.where(IncidenciaStock.estado == ESTADO_PENDIENTE)
    elif estado == "resueltos":
        stmt = stmt.where(IncidenciaStock.estado == ESTADO_RESUELTO)
    if origen:
        stmt = stmt.where(IncidenciaStock.origen == origen)
    if establecimiento_cod:
        stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    if mes:
        ini, fin = _mes_rango(mes)
        stmt = stmt.where(IncidenciaStock.detectado_en >= ini, IncidenciaStock.detectado_en < fin)

    filas = db.execute(stmt).all()
    ahora = datetime.now()
    out = []
    for inc, prod, est, rev in filas:
        cierre = inc.resuelto_en or ahora
        dias = max(0, (cierre.date() - inc.detectado_en.date()).days)
        out.append({
            "id": inc.id,
            "tipo": inc.tipo,
            "origen": inc.origen,
            "almacen_cod": inc.almacen_cod,
            "establecimiento_cod": est.cod_2000 if est else None,
            "establecimiento_nombre": est.nombre if est else None,
            "producto_cod": inc.medcod,
            "producto_nombre": prod.nombre,
            "codigo_siga": prod.codigo_siga,
            "lote": inc.lote,
            "estado": inc.estado,
            "detectado_en": inc.detectado_en,
            "detectado_inicial": inc.detectado_inicial,
            "valor_detectado": float(inc.valor_detectado),
            "valor_actual": float(inc.valor_actual),
            "resuelto_en": inc.resuelto_en,
            "valor_resuelto": float(inc.valor_resuelto) if inc.valor_resuelto is not None else None,
            "dias": dias,
            "revisado": rev is not None,
            "revisado_por": rev.revisado_por if rev else None,
            "revisado_en": rev.revisado_en if rev else None,
            "nota": rev.nota if rev else None,
        })
    return out


def resumen_mensual(db: Session, mes: str) -> dict:
    """En [mes]: cuántos negativos se detectaron, cuántos ya se resolvieron y
    cuántos siguen pendientes. Más el total pendiente hoy (de cualquier mes)."""
    ini, fin = _mes_rango(mes)
    en_mes = (IncidenciaStock.tipo == TIPO_NEGATIVO, IncidenciaStock.detectado_en >= ini, IncidenciaStock.detectado_en < fin)
    total = db.scalar(select(func.count()).where(*en_mes)) or 0
    resueltos = db.scalar(select(func.count()).where(*en_mes, IncidenciaStock.estado == ESTADO_RESUELTO)) or 0
    pendientes_totales = db.scalar(
        select(func.count()).where(IncidenciaStock.tipo == TIPO_NEGATIVO, IncidenciaStock.estado == ESTADO_PENDIENTE)
    ) or 0
    return {
        "mes": mes,
        "negativos": total,
        "resueltos": resueltos,
        "pendientes": total - resueltos,
        "pendientes_totales": pendientes_totales,
    }


def marcar_revision(db: Session, incidencia_id: int, revisado_por: str | None, nota: str | None) -> bool:
    inc = db.get(IncidenciaStock, incidencia_id)
    if inc is None:
        return False
    rev = db.scalar(select(RevisionStock).where(RevisionStock.incidencia_id == incidencia_id))
    if rev is None:
        rev = RevisionStock(incidencia_id=incidencia_id)
        db.add(rev)
    rev.revisado_por = revisado_por
    rev.nota = nota
    rev.revisado_en = datetime.now()
    db.commit()
    return True


def quitar_revision(db: Session, incidencia_id: int) -> None:
    rev = db.scalar(select(RevisionStock).where(RevisionStock.incidencia_id == incidencia_id))
    if rev is not None:
        db.delete(rev)
        db.commit()
