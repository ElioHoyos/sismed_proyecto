"""Lecturas de la tabla `stock` unificada (almacén por lote + EESS por producto).

Una sola consulta sirve para ambos orígenes; el filtro `origen` decide la forma
de las filas. Nunca se mezclan: o es stock del almacén, o el de un/os EESS."""
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.establecimiento import Establecimiento
from app.models.producto import Producto
from app.models.stock_almacen import (
    ORIGEN_ALMACEN,
    ORIGEN_EESS,
    ORIGEN_EESS_LOTE,
    Stock,
    StockFueraCatalogo,
)
from app.repositories.historial_stock_repository import mapa_incidencias_abiertas

# Un lote está "próximo a vencer" si vence dentro de esta ventana desde hoy.
VENTANA_PROXIMO_DIAS = 90
ESTADO_VENCIDO = "VENCIDO"
ESTADO_PROXIMO = "PROXIMO_A_VENCER"


def _filtrar_clasificacion(stmt, tipo: str | None, financiamiento: str | None, medest: str | None):
    """Tres clasificaciones independientes y combinables: MEDTIP (tipo: M/I),
    MEDPET (medpet: P/_) y MEDEST (medest: S=Soporte, _=SIS, E=Estratégico)."""
    if tipo:
        stmt = stmt.where(Producto.tipo == tipo)
    if financiamiento:
        stmt = stmt.where(Producto.medpet == financiamiento)
    if medest:
        stmt = stmt.where(Producto.medest == medest)
    return stmt


def _fila_almacen(s: Stock, p: Producto, consolidado: float) -> dict:
    return {
        "origen": ORIGEN_ALMACEN,
        "producto_cod": p.medcod,
        "producto_nombre": p.nombre,
        "codigo_siga": p.codigo_siga,
        "medtip": p.tipo,
        "medpet": p.medpet,
        "medest": p.medest,
        "establecimiento_cod": None,
        "establecimiento_nombre": None,
        "almacen_cod": s.almacen_cod,
        "lote": s.lote,
        "fecha_vcto": s.fecha_vcto,
        "saldo": float(s.cantidad),
        "saldo_consolidado": consolidado,
        "incidencia_id": None,  # se completa para negativos (ver _enriquecer_negativos)
        "revisado": False,
        "revisado_en": None,
        "nota": None,
    }


def _enriquecer_negativos(filas: list, dicts: list[dict], mapa: dict) -> list[dict]:
    """Adjunta a cada fila negativa su incidencia abierta (id + revisado + fecha
    y nota del check), para poder marcar/ver el check desde el Stock. `filas`
    trae los Stock; `dicts` los dicts ya armados en el mismo orden."""
    for s, d in zip((f[0] for f in filas), dicts):
        if s.cantidad < 0:
            inc = mapa.get((s.producto_id, s.lote))
            if inc:
                d["incidencia_id"] = inc["incidencia_id"]
                d["revisado"] = inc["revisado"]
                d["revisado_en"] = inc["revisado_en"]
                d["nota"] = inc["nota"]
    return dicts


def _listar_almacen(
    db: Session, solo_negativos: bool, tipo: str | None, financiamiento: str | None, medest: str | None
) -> list[dict]:
    stmt = (
        select(Stock, Producto)
        .join(Producto, Producto.id == Stock.producto_id)
        .where(Stock.origen == ORIGEN_ALMACEN)
        .order_by(Stock.cantidad, Producto.nombre)
    )
    if solo_negativos:
        stmt = stmt.where(Stock.cantidad < 0)
    stmt = _filtrar_clasificacion(stmt, tipo, financiamiento, medest)
    filas = db.execute(stmt).all()
    if not filas:
        return []

    # Consolidado por producto (suma de TODOS sus lotes en el almacén): si es
    # positivo, evidencia que el negativo del lote estaba oculto en el total.
    producto_ids = {s.producto_id for s, _ in filas}
    consolidado = {
        pid: float(total)
        for pid, total in db.execute(
            select(Stock.producto_id, func.sum(Stock.cantidad))
            .where(Stock.origen == ORIGEN_ALMACEN, Stock.producto_id.in_(producto_ids))
            .group_by(Stock.producto_id)
        ).all()
    }
    dicts = [_fila_almacen(s, p, consolidado.get(s.producto_id, float(s.cantidad))) for s, p in filas]
    return _enriquecer_negativos(filas, dicts, mapa_incidencias_abiertas(db, ORIGEN_ALMACEN))


def _listar_eess(
    db: Session,
    establecimiento_cod: str | None,
    solo_negativos: bool,
    tipo: str | None,
    financiamiento: str | None,
    medest: str | None,
) -> list[dict]:
    stmt = (
        select(Stock, Producto, Establecimiento)
        .join(Producto, Producto.id == Stock.producto_id)
        .join(Establecimiento, Establecimiento.id == Stock.establecimiento_id)
        .where(Stock.origen == ORIGEN_EESS)
        .order_by(Stock.cantidad, Producto.nombre)
    )
    if establecimiento_cod:
        stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    if solo_negativos:
        stmt = stmt.where(Stock.cantidad < 0)
    stmt = _filtrar_clasificacion(stmt, tipo, financiamiento, medest)
    filas = db.execute(stmt).all()
    return [
        {
            "origen": ORIGEN_EESS,
            "producto_cod": p.medcod,
            "producto_nombre": p.nombre,
            "codigo_siga": p.codigo_siga,
            "medtip": p.tipo,
            "medpet": p.medpet,
            "medest": p.medest,
            "establecimiento_cod": e.cod_2000,
            "establecimiento_nombre": e.nombre,
            "almacen_cod": None,
            "lote": None,  # el ICI es por producto, no trae lote
            "fecha_vcto": None,
            "saldo": float(s.cantidad),
            # EESS es por producto: no hay lotes que consolidar, el total es el saldo.
            "saldo_consolidado": float(s.cantidad),
            "incidencia_id": None,  # sin lote → sin incidencia por lote
            "revisado": False,
            "revisado_en": None,
            "nota": None,
        }
        for s, p, e in filas
    ]


def _listar_eess_lote(
    db: Session,
    establecimiento_cod: str,
    solo_negativos: bool,
    tipo: str | None,
    financiamiento: str | None,
    medest: str | None,
) -> list[dict]:
    """Stock POR LOTE de un establecimiento con SISMED propio (mismo tratamiento
    que el almacén: con vencimiento y consolidado por producto para sacar a la
    luz los negativos ocultos a nivel de lote)."""
    stmt = (
        select(Stock, Producto, Establecimiento)
        .join(Producto, Producto.id == Stock.producto_id)
        .join(Establecimiento, Establecimiento.id == Stock.establecimiento_id)
        .where(Stock.origen == ORIGEN_EESS_LOTE, Establecimiento.cod_2000 == establecimiento_cod)
        .order_by(Stock.cantidad, Producto.nombre)
    )
    if solo_negativos:
        stmt = stmt.where(Stock.cantidad < 0)
    stmt = _filtrar_clasificacion(stmt, tipo, financiamiento, medest)
    filas = db.execute(stmt).all()
    if not filas:
        return []

    est_id = filas[0][0].establecimiento_id
    producto_ids = {s.producto_id for s, _, _ in filas}
    consolidado = {
        pid: float(total)
        for pid, total in db.execute(
            select(Stock.producto_id, func.sum(Stock.cantidad))
            .where(
                Stock.origen == ORIGEN_EESS_LOTE,
                Stock.establecimiento_id == est_id,
                Stock.producto_id.in_(producto_ids),
            )
            .group_by(Stock.producto_id)
        ).all()
    }
    dicts = [
        {
            "origen": ORIGEN_EESS_LOTE,
            "producto_cod": p.medcod,
            "producto_nombre": p.nombre,
            "codigo_siga": p.codigo_siga,
            "medtip": p.tipo,
            "medpet": p.medpet,
            "medest": p.medest,
            "establecimiento_cod": e.cod_2000,
            "establecimiento_nombre": e.nombre,
            "almacen_cod": None,
            "lote": s.lote,
            "fecha_vcto": s.fecha_vcto,
            "saldo": float(s.cantidad),
            "saldo_consolidado": consolidado.get(s.producto_id, float(s.cantidad)),
            "incidencia_id": None,
            "revisado": False,
            "revisado_en": None,
            "nota": None,
        }
        for s, p, e in filas
    ]
    return _enriquecer_negativos(filas, dicts, mapa_incidencias_abiertas(db, ORIGEN_EESS_LOTE, establecimiento_cod))


def establecimiento_tiene_lote(db: Session, establecimiento_cod: str) -> bool:
    """¿Este establecimiento aportó stock POR LOTE (archivo MSTKALMDE)?"""
    return db.scalar(
        select(Stock.id)
        .join(Establecimiento, Establecimiento.id == Stock.establecimiento_id)
        .where(Stock.origen == ORIGEN_EESS_LOTE, Establecimiento.cod_2000 == establecimiento_cod)
        .limit(1)
    ) is not None


def establecimientos_con_lote(db: Session) -> list[dict]:
    """Establecimientos que aportaron stock por lote — para poder ver sus
    negativos por lote y sus vencimientos (los de solo-ICI no aplican)."""
    filas = db.execute(
        select(Establecimiento.cod_2000, Establecimiento.nombre)
        .join(Stock, Stock.establecimiento_id == Establecimiento.id)
        .where(Stock.origen == ORIGEN_EESS_LOTE)
        .distinct()
        .order_by(Establecimiento.nombre)
    ).all()
    return [{"cod_2000": c, "nombre": n} for c, n in filas]


def listar_stock(
    db: Session,
    origen: str,
    establecimiento_cod: str | None = None,
    solo_negativos: bool = False,
    tipo: str | None = None,
    financiamiento: str | None = None,
    medest: str | None = None,
) -> list[dict]:
    """origen ALMACEN → por lote (con consolidado). EESS → si el puesto aportó
    stock por lote (MSTKALMDE), por lote con vencimiento y consolidado (como el
    almacén); si solo tiene ICI, por producto. `tipo`/`financiamiento`/`medest`
    filtran por clasificación."""
    if origen == ORIGEN_ALMACEN:
        return _listar_almacen(db, solo_negativos, tipo, financiamiento, medest)
    if establecimiento_cod and establecimiento_tiene_lote(db, establecimiento_cod):
        return _listar_eess_lote(db, establecimiento_cod, solo_negativos, tipo, financiamiento, medest)
    return _listar_eess(db, establecimiento_cod, solo_negativos, tipo, financiamiento, medest)


def stock_es_por_lote(db: Session, origen: str, establecimiento_cod: str | None) -> bool:
    """Si la vista de stock resultante es por lote (almacén, o EESS con lote)."""
    if origen == ORIGEN_ALMACEN:
        return True
    return bool(establecimiento_cod) and establecimiento_tiene_lote(db, establecimiento_cod)


def listar_fuera_catalogo(
    db: Session, origen: str, establecimiento_cod: str | None = None
) -> list[dict]:
    """Productos con stock por lote que NO están en el catálogo del almacén (no se
    importan; el puesto los maneja por vía externa). Dato a revisar, no un error.
    Del almacén (origen ALMACEN) o de un/os establecimiento(s) (origen EESS)."""
    stmt = (
        select(StockFueraCatalogo, Establecimiento)
        .outerjoin(Establecimiento, Establecimiento.id == StockFueraCatalogo.establecimiento_id)
        .order_by(StockFueraCatalogo.medcod, StockFueraCatalogo.lote)
    )
    if origen == ORIGEN_ALMACEN:
        stmt = stmt.where(StockFueraCatalogo.origen == ORIGEN_ALMACEN)
    else:
        stmt = stmt.where(StockFueraCatalogo.origen == ORIGEN_EESS_LOTE)
        if establecimiento_cod:
            stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    return [
        {
            "medcod": s.medcod,
            "lote": s.lote,
            "fecha_vcto": s.fecha_vcto,
            "saldo": float(s.cantidad),
            "precio": float(s.precio) if s.precio is not None else None,
            "reg_sanitario": s.reg_sanitario,
            "establecimiento_cod": e.cod_2000 if e else None,
            "establecimiento_nombre": e.nombre if e else None,
        }
        for s, e in db.execute(stmt).all()
    ]


def listar_vencimientos(
    db: Session,
    hoy: date,
    estado: str | None = None,
    tipo: str | None = None,
    financiamiento: str | None = None,
    medest: str | None = None,
    fuente: str | None = ORIGEN_ALMACEN,
    establecimiento_cod: str | None = None,
) -> list[dict]:
    """Lotes con stock > 0 VENCIDOS (fecha_vcto < hoy) o PRÓXIMOS A VENCER
    (dentro de `VENTANA_PROXIMO_DIAS` días). Aplica al stock POR LOTE: el almacén
    y/o los establecimientos que aportaron stock por lote (MSTKALMDE) — el ICI no
    trae lote ni vencimiento, esos puestos no tienen vencimientos.

    `fuente`: ALMACEN (por defecto) → solo almacén; EESS_LOTE → establecimientos
    (uno vía `establecimiento_cod`, o todos); None → almacén + establecimientos.
    Los estados se calculan contra `hoy` (no precalculados). Orden por fecha
    ascendente (lo más urgente primero)."""
    if fuente == ORIGEN_ALMACEN:
        origenes = [ORIGEN_ALMACEN]
    elif fuente == ORIGEN_EESS_LOTE:
        origenes = [ORIGEN_EESS_LOTE]
    else:
        origenes = [ORIGEN_ALMACEN, ORIGEN_EESS_LOTE]

    limite = hoy + timedelta(days=VENTANA_PROXIMO_DIAS)
    stmt = (
        select(Stock, Producto, Establecimiento)
        .join(Producto, Producto.id == Stock.producto_id)
        .outerjoin(Establecimiento, Establecimiento.id == Stock.establecimiento_id)
        .where(
            Stock.origen.in_(origenes),
            Stock.cantidad > 0,
            Stock.fecha_vcto.isnot(None),
            Stock.fecha_vcto <= limite,  # vencido (< hoy) o próximo (<= hoy+90)
        )
        .order_by(Stock.fecha_vcto)
    )
    if establecimiento_cod:
        stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    stmt = _filtrar_clasificacion(stmt, tipo, financiamiento, medest)
    filas = db.execute(stmt).all()

    resultado: list[dict] = []
    for s, p, e in filas:
        est = ESTADO_VENCIDO if s.fecha_vcto < hoy else ESTADO_PROXIMO
        if estado and est != estado:
            continue
        resultado.append({
            "codigo_siga": p.codigo_siga,
            "producto_cod": p.medcod,
            "producto_nombre": p.nombre,
            "medtip": p.tipo,
            "medpet": p.medpet,
            "medest": p.medest,
            "lote": s.lote,
            "fecha_vcto": s.fecha_vcto,
            "dias_restantes": (s.fecha_vcto - hoy).days,
            "saldo": float(s.cantidad),
            "estado": est,
            "origen": s.origen,
            "establecimiento_cod": e.cod_2000 if e else None,
            "establecimiento_nombre": e.nombre if e else None,
            "almacen_cod": s.almacen_cod,
        })
    return resultado
