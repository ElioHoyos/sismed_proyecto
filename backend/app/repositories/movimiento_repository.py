"""Consultas sobre la tabla `movimiento` (kardex): kardex por producto con saldo
corriente, consumo fino por día/semana/mes, y clasificación de salidas por
categoría. Nunca se toca ni se devuelve dato de paciente (la tabla no lo tiene)."""
import unicodedata
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calc_cpma_red import CalcCpmaRed
from app.models.establecimiento import Establecimiento
from app.models.movimiento import Movimiento
from app.models.producto import Producto


def _norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", (t or "").lower())
    return "".join(c for c in t if not unicodedata.combining(c)).strip()


def resolver_producto(db: Session, texto: str) -> Producto | None:
    """Producto por código exacto (medcod/SIGA) o por nombre parcial."""
    q = (texto or "").strip()
    if not q:
        return None
    p = db.scalar(select(Producto).where((Producto.medcod == q) | (Producto.codigo_siga == q)))
    if p:
        return p
    qn = f"%{_norm(q)}%"
    return db.scalar(select(Producto).where(func.lower(Producto.nombre).like(qn)).order_by(Producto.nombre).limit(1))


def establecimientos_con_movimientos(db: Session) -> list[dict]:
    filas = db.execute(
        select(Establecimiento.cod_2000, Establecimiento.nombre)
        .join(Movimiento, Movimiento.establecimiento_id == Establecimiento.id)
        .distinct()
        .order_by(Establecimiento.nombre)
    ).all()
    return [{"cod_2000": c, "nombre": n} for c, n in filas]


def _filtros(stmt, establecimiento_cod, desde, hasta):
    if establecimiento_cod:
        stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    if desde:
        stmt = stmt.where(Movimiento.fecha_emision >= desde)
    if hasta:
        # `hasta` es un día inclusivo; fecha_emision es datetime → hasta el fin del día.
        stmt = stmt.where(Movimiento.fecha_emision < hasta + timedelta(days=1))
    return stmt


# ── PASO 2: Kardex (histórico E/S con saldo corriente) ─────────────────────

def kardex(db, producto: Producto, establecimiento_cod=None, desde=None, hasta=None) -> list[dict]:
    stmt = (
        select(Movimiento, Establecimiento.cod_2000, Establecimiento.nombre)
        .join(Establecimiento, Establecimiento.id == Movimiento.establecimiento_id)
        .where(Movimiento.producto_id == producto.id)
        .order_by(Movimiento.establecimiento_id, Movimiento.fecha_emision, Movimiento.id)
    )
    stmt = _filtros(stmt, establecimiento_cod, desde, hasta)
    filas = db.execute(stmt).all()
    salida: list[dict] = []
    saldo = 0.0
    est_actual = None
    for m, cod, nombre in filas:
        if cod != est_actual:  # el saldo corriente es por establecimiento
            saldo = 0.0
            est_actual = cod
        delta = float(m.cantidad) if m.tipo == "E" else -float(m.cantidad)
        saldo += delta
        salida.append({
            "fecha": m.fecha_emision,
            "tipo": m.tipo,
            "lote": m.lote,
            "fecha_vcto": m.fecha_vcto,
            "cantidad": float(m.cantidad),
            "categoria": m.categoria,
            "establecimiento_cod": cod,
            "establecimiento_nombre": nombre,
            "saldo": saldo,
        })
    return salida


# ── PASO 3: Consumo fino (salidas por día/semana/mes) ──────────────────────

_GRAN = {
    "dia": func.date_format(Movimiento.fecha_emision, "%Y-%m-%d"),
    "semana": func.date_format(Movimiento.fecha_emision, "%x-S%v"),  # año-Semana ISO
    "mes": func.date_format(Movimiento.fecha_emision, "%Y-%m"),
}


def consumo(db, producto: Producto, establecimiento_cod=None, granularidad="mes", desde=None, hasta=None) -> list[dict]:
    """Salidas (consumo) agrupadas por período. Solo tipo 'S'."""
    expr = _GRAN.get(granularidad, _GRAN["mes"])
    stmt = (
        select(expr.label("periodo"), func.sum(Movimiento.cantidad), func.count())
        .join(Establecimiento, Establecimiento.id == Movimiento.establecimiento_id)
        .where(Movimiento.producto_id == producto.id, Movimiento.tipo == "S")
        .group_by("periodo")
        .order_by("periodo")
    )
    stmt = _filtros(stmt, establecimiento_cod, desde, hasta)
    return [{"periodo": p, "salidas": float(s or 0), "movimientos": n} for p, s, n in db.execute(stmt).all()]


def cpma_de_referencia(db, producto: Producto) -> float | None:
    """CPMA a nivel red (para comparar el consumo real contra el calculado)."""
    v = db.scalar(
        select(CalcCpmaRed.cpma)
        .where(CalcCpmaRed.producto_id == producto.id)
        .order_by(CalcCpmaRed.periodo.desc())
        .limit(1)
    )
    return float(v) if v is not None else None


# ── PASO 4: Clasificación de salidas por categoría ─────────────────────────

def clasificacion_salidas(db, producto: Producto, establecimiento_cod=None, desde=None, hasta=None) -> list[dict]:
    stmt = (
        select(Movimiento.categoria, func.sum(Movimiento.cantidad), func.count())
        .join(Establecimiento, Establecimiento.id == Movimiento.establecimiento_id)
        .where(Movimiento.producto_id == producto.id, Movimiento.tipo == "S")
        .group_by(Movimiento.categoria)
        .order_by(func.sum(Movimiento.cantidad).desc())
    )
    stmt = _filtros(stmt, establecimiento_cod, desde, hasta)
    return [
        {"categoria": cat or "NOMINAL", "salidas": float(s or 0), "movimientos": n}
        for cat, s, n in db.execute(stmt).all()
    ]
