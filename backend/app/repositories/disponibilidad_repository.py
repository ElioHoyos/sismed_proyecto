"""Lecturas de disponibilidad/situación/requisición — todo desde
calc_cpma/calc_cpma_red, nada se calcula al vuelo aquí."""
from collections import defaultdict
from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.calc_cpma import CalcCpma
from app.models.calc_cpma_red import CalcCpmaRed
from app.models.establecimiento import Establecimiento
from app.models.ici import Ici
from app.models.producto import Producto
from app.services.cpma import requisicion_sugerida

MESES_ES = (
    "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
    "JULIO", "AGOSTO", "SETIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
)


def _ventana_12_meses(periodo: date) -> list[tuple[int, int]]:
    base = periodo.year * 12 + (periodo.month - 1)
    return [((base - i) // 12, (base - i) % 12 + 1) for i in range(11, -1, -1)]


def _meses_vacios(periodo: date) -> list[dict]:
    return [
        {"anio": anio, "mes": mes, "nombre": MESES_ES[mes - 1], "consumo": 0.0}
        for anio, mes in _ventana_12_meses(periodo)
    ]


def _consumos_mensuales_establecimiento(
    db: Session, pares: set[tuple[int, int]], periodo: date
) -> dict[tuple[int, int], list[dict]]:
    """Desglose MES01..MES12 por (establecimiento_id, producto_id), en la
    misma ventana de 12 meses que calc_cpma. Un mes sin fila en `ici` = 0,
    no se distingue de un mes reportado en 0 (mismo criterio que el CPMA)."""
    if not pares:
        return {}

    ventana = _ventana_12_meses(periodo)
    yyyymm_ini = ventana[0][0] * 100 + ventana[0][1]
    yyyymm_fin = ventana[-1][0] * 100 + ventana[-1][1]
    est_ids = {e for e, _ in pares}
    prod_ids = {p for _, p in pares}

    filas = db.execute(
        select(Ici.establecimiento_id, Ici.producto_id, Ici.anio, Ici.mes, Ici.consumo).where(
            Ici.establecimiento_id.in_(est_ids),
            Ici.producto_id.in_(prod_ids),
            (Ici.anio * 100 + Ici.mes).between(yyyymm_ini, yyyymm_fin),
        )
    ).all()

    consumo_por_par: dict[tuple[int, int], dict[tuple[int, int], float]] = defaultdict(dict)
    for est_id, prod_id, anio, mes, consumo in filas:
        if (est_id, prod_id) in pares:
            consumo_por_par[(est_id, prod_id)][(anio, mes)] = float(consumo)

    return {
        par: [
            {"anio": anio, "mes": mes, "nombre": MESES_ES[mes - 1],
             "consumo": consumo_por_par.get(par, {}).get((anio, mes), 0.0)}
            for anio, mes in ventana
        ]
        for par in pares
    }


def _consumos_mensuales_red(
    db: Session, producto_ids: set[int], periodo: date
) -> dict[int, list[dict]]:
    """Igual que _consumos_mensuales_establecimiento pero sumado entre
    todos los establecimientos — mismo criterio que calc_cpma_red."""
    if not producto_ids:
        return {}

    ventana = _ventana_12_meses(periodo)
    yyyymm_ini = ventana[0][0] * 100 + ventana[0][1]
    yyyymm_fin = ventana[-1][0] * 100 + ventana[-1][1]

    filas = db.execute(
        select(Ici.producto_id, Ici.anio, Ici.mes, func.sum(Ici.consumo))
        .where(
            Ici.producto_id.in_(producto_ids),
            (Ici.anio * 100 + Ici.mes).between(yyyymm_ini, yyyymm_fin),
        )
        .group_by(Ici.producto_id, Ici.anio, Ici.mes)
    ).all()

    consumo_por_prod: dict[int, dict[tuple[int, int], float]] = defaultdict(dict)
    for prod_id, anio, mes, consumo in filas:
        consumo_por_prod[prod_id][(anio, mes)] = float(consumo)

    return {
        prod_id: [
            {"anio": anio, "mes": mes, "nombre": MESES_ES[mes - 1],
             "consumo": consumo_por_prod.get(prod_id, {}).get((anio, mes), 0.0)}
            for anio, mes in ventana
        ]
        for prod_id in producto_ids
    }


def _clasificacion_producto(prod: Producto) -> dict:
    """Códigos crudos del catálogo (tal cual el doc): CODIGO SIGA, MEDTIP, MEDPET, MEDEST, FF."""
    return {
        "codigo_siga": prod.codigo_siga,
        "medtip": prod.tipo,
        "medpet": prod.medpet,
        "medest": prod.medest,
        "ff": prod.forma_farma,
    }


def _fila_a_dict_establecimiento(c: CalcCpma, est: Establecimiento, prod: Producto) -> dict:
    return {
        "establecimiento_cod": est.cod_2000,
        "establecimiento_nombre": est.nombre,
        "producto_cod": prod.medcod,
        "producto_nombre": prod.nombre,
        **_clasificacion_producto(prod),
        "sumames": c.sumames,
        "contador": c.contador,
        "cpma": c.cpma,
        "stock_red": c.stock_red,
        "stock_aem": c.stock_aem,
        "dispo": c.dispo,
        "dispo_total": c.dispo_total,
        "situacion": c.situacion,
        "situacion_total": c.situacion_total,
    }


def listar_disponibilidad(
    db: Session,
    establecimiento_cod: str | None = None,
    producto_cod: str | None = None,
    situacion: str | None = None,
    periodo: date | None = None,
) -> tuple[date | None, list[dict]]:
    periodo_usado = periodo or db.scalar(select(func.max(CalcCpma.periodo)))
    if periodo_usado is None:
        return None, []

    stmt = (
        select(CalcCpma, Establecimiento, Producto)
        .join(Establecimiento, Establecimiento.id == CalcCpma.establecimiento_id)
        .join(Producto, Producto.id == CalcCpma.producto_id)
        .where(CalcCpma.periodo == periodo_usado)
        .order_by(Establecimiento.nombre, Producto.nombre)
    )
    if establecimiento_cod:
        stmt = stmt.where(Establecimiento.cod_2000 == establecimiento_cod)
    if producto_cod:
        stmt = stmt.where(Producto.medcod == producto_cod)
    if situacion:
        stmt = stmt.where(CalcCpma.situacion == situacion)

    filas = db.execute(stmt).all()
    pares = {(c.establecimiento_id, c.producto_id) for c, _, _ in filas}
    meses_por_par = _consumos_mensuales_establecimiento(db, pares, periodo_usado)

    return periodo_usado, [
        {
            **_fila_a_dict_establecimiento(c, est, prod),
            "meses": meses_por_par.get((c.establecimiento_id, c.producto_id), _meses_vacios(periodo_usado)),
        }
        for c, est, prod in filas
    ]


def listar_disponibilidad_red(
    db: Session,
    producto_cod: str | None = None,
    situacion: str | None = None,
    periodo: date | None = None,
) -> tuple[date | None, list[dict]]:
    periodo_usado = periodo or db.scalar(select(func.max(CalcCpmaRed.periodo)))
    if periodo_usado is None:
        return None, []

    stmt = (
        select(CalcCpmaRed, Producto)
        .join(Producto, Producto.id == CalcCpmaRed.producto_id)
        .where(CalcCpmaRed.periodo == periodo_usado)
        .order_by(Producto.nombre)
    )
    if producto_cod:
        stmt = stmt.where(Producto.medcod == producto_cod)
    if situacion:
        stmt = stmt.where(CalcCpmaRed.situacion == situacion)

    filas = db.execute(stmt).all()
    producto_ids = {c.producto_id for c, _ in filas}
    meses_por_prod = _consumos_mensuales_red(db, producto_ids, periodo_usado)

    return periodo_usado, [
        {
            "producto_cod": prod.medcod,
            "producto_nombre": prod.nombre,
            **_clasificacion_producto(prod),
            "sumames": c.sumames,
            "contador": c.contador,
            "cpma": c.cpma,
            "stock_red": c.stock_red,
            "stock_aem": c.stock_aem,
            "dispo": c.dispo,
            "dispo_total": c.dispo_total,
            "situacion": c.situacion,
            "situacion_total": c.situacion_total,
            "meses": meses_por_prod.get(c.producto_id, _meses_vacios(periodo_usado)),
        }
        for c, prod in filas
    ]


def _distribucion(conteos: dict[str, int]) -> list[dict]:
    total = sum(conteos.values())
    dist = [
        {"situacion": s, "cantidad": n, "porcentaje": round(100 * n / total, 1) if total else 0.0}
        for s, n in conteos.items()
    ]
    dist.sort(key=lambda f: f["cantidad"], reverse=True)
    return dist


def resumen_situacion_red(db: Session, periodo: date | None = None) -> tuple[date | None, dict]:
    """% de situación de la red, DOS indicadores independientes por MEDEST:
    Soporte (S) y SIS (_). Los Estratégicos (E) se excluyen del universo, según
    la norma. SIEMPRE desde calc_cpma_red (una fila por producto): el stock del
    almacén se repite por establecimiento en calc_cpma e inflaría el agregado."""
    vacio = {"soporte": [], "sis": [], "total_soporte": 0, "total_sis": 0}
    periodo_usado = periodo or db.scalar(select(func.max(CalcCpmaRed.periodo)))
    if periodo_usado is None:
        return None, vacio

    filas = db.execute(
        select(Producto.medest, CalcCpmaRed.situacion, func.count())
        .join(Producto, Producto.id == CalcCpmaRed.producto_id)
        .where(CalcCpmaRed.periodo == periodo_usado, Producto.medest.in_(("S", "_")))
        .group_by(Producto.medest, CalcCpmaRed.situacion)
    ).all()

    conteos: dict[str, dict[str, int]] = {"S": {}, "_": {}}
    for medest, situacion, n in filas:
        conteos[medest][situacion] = n

    soporte = _distribucion(conteos["S"])
    sis = _distribucion(conteos["_"])
    return periodo_usado, {
        "soporte": soporte,
        "sis": sis,
        "total_soporte": sum(f["cantidad"] for f in soporte),
        "total_sis": sum(f["cantidad"] for f in sis),
    }


def obtener_requisicion(
    db: Session,
    producto_cod: str,
    establecimiento_cod: str | None,
    periodo: date | None,
    meses_a_cubrir: int,
) -> dict | None:
    """Con establecimiento_cod: requisición local. Sin él: nivel red
    (almacén pidiendo al proveedor). Solo la fórmula final (parametrizada
    por meses_a_cubrir) se calcula al vuelo; CPMA y stock salen ya calculados."""
    producto = db.scalar(select(Producto).where(Producto.medcod == producto_cod))
    if producto is None:
        return None

    if establecimiento_cod:
        establecimiento = db.scalar(
            select(Establecimiento).where(Establecimiento.cod_2000 == establecimiento_cod)
        )
        if establecimiento is None:
            return None
        periodo_usado = periodo or db.scalar(
            select(func.max(CalcCpma.periodo)).where(
                CalcCpma.establecimiento_id == establecimiento.id,
                CalcCpma.producto_id == producto.id,
            )
        )
        if periodo_usado is None:
            return None
        fila = db.scalar(
            select(CalcCpma).where(
                CalcCpma.establecimiento_id == establecimiento.id,
                CalcCpma.producto_id == producto.id,
                CalcCpma.periodo == periodo_usado,
            )
        )
        if fila is None:
            return None
        nivel, cod = "establecimiento", establecimiento_cod
    else:
        periodo_usado = periodo or db.scalar(
            select(func.max(CalcCpmaRed.periodo)).where(CalcCpmaRed.producto_id == producto.id)
        )
        if periodo_usado is None:
            return None
        fila = db.scalar(
            select(CalcCpmaRed).where(
                CalcCpmaRed.producto_id == producto.id, CalcCpmaRed.periodo == periodo_usado
            )
        )
        if fila is None:
            return None
        nivel, cod = "red", None

    stock_disponible = Decimal(fila.stock_red) + Decimal(fila.stock_aem)
    cantidad = requisicion_sugerida(Decimal(fila.cpma), stock_disponible, meses_a_cubrir)

    return {
        "nivel": nivel,
        "establecimiento_cod": cod,
        "producto_cod": producto.medcod,
        "producto_nombre": producto.nombre,
        "periodo": periodo_usado,
        "cpma": fila.cpma,
        "stock_disponible": stock_disponible,
        "meses_a_cubrir": meses_a_cubrir,
        "cantidad_requerida": cantidad,
    }
