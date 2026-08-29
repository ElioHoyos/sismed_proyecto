"""Consolidado de Red: cruza el ICI (consumo + cálculos, desde calc_cpma_red) con
el estado de compra de CENARES (archivo + ediciones del doc). Es el DISPO_RED que
el doc arma a mano con VLOOKUPs. Siempre a nivel de RED (nunca por establecimiento)."""
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.ici import Ici
from app.models.producto import Producto
from app.repositories.compra_repository import CAMPOS_EDITABLES, mapa_compra, mapa_edicion
from app.repositories.disponibilidad_repository import listar_disponibilidad_red


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else None


def _mapa_precio(db: Session, periodo: date) -> dict[str, float]:
    """PRECIO por medcod en el mes de cierre (del ICI)."""
    filas = db.execute(
        select(Producto.medcod, func.max(Ici.precio))
        .join(Producto, Producto.id == Ici.producto_id)
        .where(Ici.anio == periodo.year, Ici.mes == periodo.month)
        .group_by(Producto.medcod)
    ).all()
    return {medcod: float(p) for medcod, p in filas if p is not None}


def _compra_final(reg: dict | None, edits: dict) -> dict:
    """Mezcla archivo + edición: la edición del doc gana sobre el valor del
    archivo. Todo el bloque es editable menos TIPO PRODUCTO. Las fechas base
    (F.CONV/F.BP) se devuelven como ISO; si el doc las editó, gana su texto
    libre (ej. 'NOVIEMBRE 2026'). Marca los campos editados y si no hay registro
    del archivo (para mostrar 'Sin compra centralizada')."""
    f = reg or {}

    def val(campo: str, base):
        """Valor final del campo: la edición del doc si existe, si no el base."""
        return edits[campo] if campo in edits else base

    return {
        # Único no editable (viene del archivo).
        "tipo_producto": f.get("tipo_producto"),
        # Editables — la edición gana sobre el archivo.
        "procedimiento": val("procedimiento", f.get("procedimiento")),
        "estado_situacion": val("estado_situacion", f.get("estado_situacion")),
        "observacion_estado": val("observacion_estado", f.get("observacion_estado")),
        "reg_siga_situacion": val("reg_siga_situacion", f.get("reg_siga_situacion")),
        "reg_siga_observacion": val("reg_siga_observacion", f.get("reg_siga_observacion")),
        "contratista": val("contratista", f.get("contratista")),
        "nro_contrato": val("nro_contrato", f.get("nro_contrato")),
        "fecha_convocatoria": val("fecha_convocatoria", _iso(f.get("fecha_convocatoria"))),
        "fecha_buena_pro": val("fecha_buena_pro", _iso(f.get("fecha_buena_pro"))),
        "fecha_entrega_texto": val("fecha_entrega_texto", f.get("fecha_entrega_texto")),
        "observacion": val("observacion", f.get("observacion")),
        "editados": [c for c in CAMPOS_EDITABLES if c in edits],
        "sin_registro": reg is None and not edits,
    }


def listar_consolidado(
    db: Session, periodo: date | None = None, compra_anio: int | None = None
) -> tuple[date | None, list[dict]]:
    """Filas de la vista consolidada de red + precio + bloque de compra cruzado."""
    per_usado, filas = listar_disponibilidad_red(db, periodo=periodo)
    if per_usado is None:
        return None, []

    precios = _mapa_precio(db, per_usado)
    mfile = mapa_compra(db, compra_anio) if compra_anio is not None else {}
    medit = mapa_edicion(db, compra_anio) if compra_anio is not None else {}

    for f in filas:
        f["precio"] = precios.get(f["producto_cod"], 0.0)
        f["compra"] = _compra_final(mfile.get(f["producto_cod"]), medit.get(f["producto_cod"], {}))

    return per_usado, filas
