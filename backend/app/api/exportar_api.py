"""Endpoints de exportación (Excel / PDF). Reciben los MISMOS parámetros de
filtro que las consultas y devuelven el archivo con exactamente esas filas —
la exportación es dinámica, no la tabla completa. Ver app/services/exportar.py."""
from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.models.stock_almacen import ORIGEN_ALMACEN, ORIGEN_EESS, ORIGEN_EESS_LOTE
from app.repositories.disponibilidad_repository import (
    listar_disponibilidad,
    listar_disponibilidad_red,
)
from app.repositories.stock_repository import (
    ESTADO_PROXIMO,
    ESTADO_VENCIDO,
    listar_stock,
    listar_vencimientos,
    stock_es_por_lote,
)
from app.services.exportar import (
    ESTADO_VENC_COLORES,
    SITUACION_COLORES,
    Columna,
    generar_excel,
    generar_pdf,
    nombre_archivo,
)

router = APIRouter(prefix="/api", tags=["exportar"])

XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
PDF = "application/pdf"

_SIG_MEDTIP = {"M": "Medicamento", "I": "Insumo"}
_SIG_MEDPET = {"P": "Petitorio", "_": "SIS"}
_SIG_MEDEST = {"S": "Soporte", "_": "SIS", "E": "Estratégico"}


def _periodo(periodo: str | None) -> date | None:
    if not periodo:
        return None
    try:
        a, m = periodo.split("-")
        return date(int(a), int(m), 1)
    except (ValueError, AttributeError):
        raise HTTPException(400, f"periodo inválido: {periodo!r}")


def _buscar(filas: list[dict], q: str | None, campos: list[str]) -> list[dict]:
    if not q:
        return filas
    ql = q.strip().lower()
    return [f for f in filas if any(ql in str(f.get(c) or "").lower() for c in campos)]


def _clasif(filas, tipo, fin, medest) -> list[dict]:
    return [
        f
        for f in filas
        if (not tipo or f.get("medtip") == tipo)
        and (not fin or f.get("medpet") == fin)
        and (not medest or f.get("medest") == medest)
    ]


def _linea_filtros(**kv) -> str:
    activos = [f"{k}={v}" for k, v in kv.items() if v not in (None, "", False)]
    return " · ".join(activos) if activos else "ninguno"


def _entregar(formato: str, columnas, filas, titulo, meta, resumen, modulo, partes) -> Response:
    formato = (formato or "xlsx").lower()
    if formato == "pdf":
        contenido = generar_pdf(titulo, meta, columnas, filas, resumen=resumen)
        return Response(
            contenido,
            media_type=PDF,
            headers={"Content-Disposition": f'attachment; filename="{nombre_archivo(modulo, partes, "pdf")}"'},
        )
    contenido = generar_excel(titulo, meta, columnas, filas)
    return Response(
        contenido,
        media_type=XLSX,
        headers={"Content-Disposition": f'attachment; filename="{nombre_archivo(modulo, partes, "xlsx")}"'},
    )


def _resumen_situacion(filas, clave) -> list[str]:
    c = Counter(f.get(clave) for f in filas if f.get(clave))
    return [f"{s}: {n}" for s, n in c.most_common()]


# ── Disponibilidad ────────────────────────────────────────────────────────

_COLS_PRODUCTO = [
    Columna("codigo_siga", "Código SIGA"),
    Columna("producto_cod", "Código"),
    Columna("producto_nombre", "Medicamento"),
    Columna("medtip", "M/I"),
    Columna("medpet", "_/P"),
    Columna("medest", "E/S/_"),
    Columna("ff", "FF"),
]


def _flatten_meses(filas):
    if not filas:
        return []
    meses = filas[0].get("meses") or []
    cols = []
    for idx, m in enumerate(meses):
        clave = f"_mes{idx}"
        cols.append(Columna(clave, m["nombre"][:3].capitalize(), "entero"))
        for f in filas:
            lista = f.get("meses") or []
            f[clave] = lista[idx]["consumo"] if idx < len(lista) else None
    return cols


@router.get("/disponibilidad/export")
def exportar_disponibilidad(
    formato: str = Query("xlsx"),
    vista: str = Query("red", description="red | establecimiento"),
    establecimiento_cod: str | None = None,
    periodo: str | None = None,
    situacion: str | None = None,
    tipo: str | None = None,
    financiamiento: str | None = None,
    medest: str | None = None,
    buscar: str | None = None,
    db: Session = Depends(get_db),
):
    per = _periodo(periodo)
    es_red = vista != "establecimiento"
    if es_red:
        per_usado, filas = listar_disponibilidad_red(db, situacion=situacion, periodo=per)
    else:
        per_usado, filas = listar_disponibilidad(
            db, establecimiento_cod=establecimiento_cod, situacion=situacion, periodo=per
        )
    filas = _clasif(filas, tipo, financiamiento, medest)
    filas = _buscar(filas, buscar, ["producto_nombre", "producto_cod", "codigo_siga"])

    clave_sit = "situacion_total" if es_red else "situacion"
    clave_dispo = "dispo_total" if es_red else "dispo"
    est_nombre = filas[0].get("establecimiento_nombre") if (filas and not es_red) else None
    per_txt = per_usado.strftime("%Y-%m") if per_usado else "—"

    meta = [
        ("Vista", "Red + AEM (consolidada)" if es_red else "EESS (por establecimiento)"),
        ("Establecimiento", est_nombre or ("Toda la red" if es_red else (establecimiento_cod or "—"))),
        ("Periodo", per_txt),
        ("Filtros", _linea_filtros(situacion=situacion, tipo=tipo, financiamiento=financiamiento, medest=medest, buscar=buscar)),
    ]
    resumen = [f"{len(filas)} productos"] + _resumen_situacion(filas, clave_sit)

    if (formato or "").lower() == "pdf":
        columnas = [
            Columna("producto_nombre", "Medicamento"),
            Columna("codigo_siga", "Código SIGA"),
            Columna("cpma", "CPMA", "decimal"),
            Columna("stock_red", "Stock Red", "entero"),
            Columna(clave_dispo, "Disponib. (meses)", "decimal"),
            Columna(clave_sit, "Situación", colores=SITUACION_COLORES),
        ]
    else:
        cols_stock = (
            [
                Columna("stock_red", "Stock Red", "entero"),
                Columna("stock_aem", "Stock AEM", "entero"),
                Columna("dispo_total", "Meses (total)", "decimal"),
                Columna("situacion_total", "Situación", colores=SITUACION_COLORES),
            ]
            if es_red
            else [
                Columna("stock_red", "Stock Red", "entero"),
                Columna("dispo", "Meses (EESS)", "decimal"),
                Columna("situacion", "Situación", colores=SITUACION_COLORES),
            ]
        )
        columnas = (
            _COLS_PRODUCTO
            + _flatten_meses(filas)
            + [
                Columna("sumames", "Consumo 12m", "entero"),
                Columna("contador", "Meses c/cons.", "entero"),
                Columna("cpma", "CPMA", "decimal"),
            ]
            + cols_stock
        )

    partes = ["red" if es_red else slug_est(est_nombre or establecimiento_cod), per_txt]
    return _entregar(formato, columnas, filas, "Disponibilidad — tabla maestra", meta, resumen, "disponibilidad", partes)


def slug_est(v: str | None) -> str:
    return v or "eess"


# ── Stock ─────────────────────────────────────────────────────────────────

@router.get("/stock/export")
def exportar_stock(
    formato: str = Query("xlsx"),
    origen: str = Query("ALMACEN"),
    establecimiento_cod: str | None = None,
    solo_negativos: bool = False,
    tipo: str | None = None,
    financiamiento: str | None = None,
    medest: str | None = None,
    buscar: str | None = None,
    db: Session = Depends(get_db),
):
    origen = origen.upper()
    if origen not in (ORIGEN_ALMACEN, ORIGEN_EESS):
        raise HTTPException(400, "origen debe ser 'ALMACEN' o 'EESS'.")
    es_almacen = origen == ORIGEN_ALMACEN
    est_cod = establecimiento_cod if not es_almacen else None
    filas = listar_stock(
        db,
        origen=origen,
        establecimiento_cod=est_cod,
        solo_negativos=solo_negativos,
        tipo=tipo,
        financiamiento=financiamiento,
        medest=medest,
    )
    filas = _buscar(filas, buscar, ["producto_nombre", "producto_cod", "codigo_siga", "lote"])
    # Por lote = almacén, o un puesto que aportó stock por lote (MSTKALMDE).
    por_lote = stock_es_por_lote(db, origen, est_cod)

    negativos = sum(1 for f in filas if f["saldo"] < 0)
    afectados = len({f["producto_cod"] for f in filas if f["saldo"] < 0})
    est_nombre = filas[0].get("establecimiento_nombre") if (filas and not es_almacen) else None
    if es_almacen:
        origen_txt = "Almacén central"
    elif por_lote:
        origen_txt = "Establecimiento (stock por lote)"
    else:
        origen_txt = "Establecimiento (ICI, por producto)"
    meta = [
        ("Origen", origen_txt),
        ("Establecimiento", est_nombre or ("—" if es_almacen else (establecimiento_cod or "Todos los puestos"))),
        ("Filtros", _linea_filtros(solo_negativos=solo_negativos, tipo=tipo, financiamiento=financiamiento, medest=medest, buscar=buscar)),
    ]
    resumen = [f"{len(filas)} {'lotes' if por_lote else 'productos'}", f"{negativos} negativos", f"{afectados} productos afectados"]

    base = [
        Columna("producto_cod", "Código"),
        Columna("codigo_siga", "Código SIGA"),
        Columna("producto_nombre", "Medicamento"),
        Columna("medtip", "M/I"),
        Columna("medpet", "_/P"),
        Columna("medest", "E/S/_"),
    ]
    if por_lote:
        # EESS por lote incluye la columna de establecimiento; el almacén no.
        columnas = base + ([] if es_almacen else [Columna("establecimiento_nombre", "Establecimiento")]) + [
            Columna("lote", "Lote"),
            Columna("fecha_vcto", "Vence", "fecha"),
            Columna("saldo", "Saldo", "decimal", resaltar_negativo=True),
            Columna("saldo_consolidado", "Total producto", "decimal"),
        ]
    else:
        columnas = base + [
            Columna("establecimiento_nombre", "Establecimiento"),
            Columna("saldo", "Saldo", "decimal", resaltar_negativo=True),
        ]

    partes = [origen.lower(), slug_est(est_nombre or (establecimiento_cod if not es_almacen else "")), "negativos" if solo_negativos else ""]
    return _entregar(formato, columnas, filas, "Stock", meta, resumen, "stock", partes)


# ── Vencimientos ──────────────────────────────────────────────────────────

@router.get("/stock/vencimientos/export")
def exportar_vencimientos(
    formato: str = Query("xlsx"),
    estado: str | None = None,
    fuente: str = Query("ALMACEN"),
    establecimiento_cod: str | None = None,
    tipo: str | None = None,
    financiamiento: str | None = None,
    medest: str | None = None,
    buscar: str | None = None,
    db: Session = Depends(get_db),
):
    estado_norm = estado.upper() if estado else None
    if estado_norm and estado_norm not in (ESTADO_VENCIDO, ESTADO_PROXIMO):
        raise HTTPException(400, "estado debe ser 'VENCIDO' o 'PROXIMO_A_VENCER'.")
    fuente = fuente.upper()
    if fuente not in ("ALMACEN", "EESS"):
        raise HTTPException(400, "fuente debe ser 'ALMACEN' o 'EESS'.")
    es_almacen = fuente == "ALMACEN"
    fuente_origen = ORIGEN_ALMACEN if es_almacen else ORIGEN_EESS_LOTE

    filas = listar_vencimientos(
        db, date.today(), estado_norm, tipo=tipo, financiamiento=financiamiento, medest=medest,
        fuente=fuente_origen, establecimiento_cod=establecimiento_cod if not es_almacen else None,
    )
    filas = _buscar(filas, buscar, ["producto_nombre", "codigo_siga", "lote", "establecimiento_nombre"])

    vencidos = [f for f in filas if f["estado"] == ESTADO_VENCIDO]
    proximos = [f for f in filas if f["estado"] == ESTADO_PROXIMO]
    # Texto amigable para la celda (el color se mapea sobre este texto) y la ubicación.
    for f in filas:
        f["estado_txt"] = "Vencido" if f["estado"] == ESTADO_VENCIDO else "Próximo a vencer"
        f["ubicacion"] = f.get("establecimiento_nombre") or "Almacén central"

    est_nombre = filas[0].get("establecimiento_nombre") if (filas and not es_almacen) else None
    if es_almacen:
        alcance = "Almacén central (el ICI no trae lote ni vencimiento)"
    elif establecimiento_cod:
        alcance = f"Establecimiento {est_nombre or establecimiento_cod} (stock por lote)"
    else:
        alcance = "Establecimientos con stock por lote"
    meta = [
        ("Alcance", alcance),
        ("Filtros", _linea_filtros(estado=estado_norm, tipo=tipo, financiamiento=financiamiento, medest=medest, buscar=buscar)),
    ]
    resumen = [
        f"{len(vencidos)} vencidos ({sum(f['saldo'] for f in vencidos):,.0f} u.)",
        f"{len(proximos)} próximos ({sum(f['saldo'] for f in proximos):,.0f} u.)",
    ]

    columnas = [
        Columna("codigo_siga", "Código SIGA"),
        Columna("producto_nombre", "Medicamento"),
        Columna("medtip", "M/I"),
        Columna("medpet", "_/P"),
        Columna("medest", "E/S/_"),
        Columna("lote", "Lote"),
        Columna("fecha_vcto", "Vence", "fecha"),
        Columna("dias_restantes", "Días", "entero"),
        Columna("saldo", "Unidades", "entero"),
        Columna("estado_txt", "Estado", colores={"Vencido": ESTADO_VENC_COLORES["VENCIDO"], "Próximo a vencer": ESTADO_VENC_COLORES["PROXIMO_A_VENCER"]}),
    ]
    # Con varios puestos (fuente EESS sin uno fijo), agregar la columna de ubicación.
    if not es_almacen and not establecimiento_cod:
        columnas.insert(5, Columna("ubicacion", "Establecimiento"))

    titulo = "Vencimientos del almacén" if es_almacen else "Vencimientos por establecimiento"
    partes = [fuente.lower(), slug_est(est_nombre or establecimiento_cod or ""), estado_norm.lower() if estado_norm else "todos"]
    return _entregar(formato, columnas, filas, titulo, meta, resumen, "vencimientos", partes)
