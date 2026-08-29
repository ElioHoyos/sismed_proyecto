"""Lecturas de la compra centralizada (CENARES) y ediciones del doc."""
from sqlalchemy import delete, distinct, func, select
from sqlalchemy.dialects.mysql import insert as mysql_insert
from sqlalchemy.orm import Session

from app.models.compra_centralizada import CompraCentralizada, CompraEdicion

# Campos que el doc puede editar a mano en el Consolidado de Red (todo el bloque
# de compra CENARES menos TIPO PRODUCTO). En orden de columna, para que el
# `editados` y la navegación con Tab sigan el mismo orden que ve el doc.
CAMPOS_EDITABLES = (
    "procedimiento",
    "estado_situacion",
    "observacion_estado",
    "reg_siga_situacion",
    "reg_siga_observacion",
    "contratista",
    "nro_contrato",
    "fecha_convocatoria",
    "fecha_buena_pro",
    "fecha_entrega_texto",
    "observacion",
)


def _a_dict(c: CompraCentralizada) -> dict:
    return {
        "codigo_sismed": c.codigo_sismed,
        "codigo_siga": c.codigo_siga,
        "tipo_producto": c.tipo_producto,
        "procedimiento": c.procedimiento,
        "estado_situacion": c.estado_situacion,
        "observacion_estado": c.observacion_estado,
        "reg_siga_situacion": c.reg_siga_situacion,
        "reg_siga_observacion": c.reg_siga_observacion,
        "contratista": c.contratista,
        "nro_contrato": c.nro_contrato,
        "fecha_convocatoria": c.fecha_convocatoria,
        "fecha_buena_pro": c.fecha_buena_pro,
        "fecha_entrega": c.fecha_entrega,
        "fecha_entrega_texto": c.fecha_entrega_texto,
        "observacion": c.observacion,
    }


def anios_disponibles(db: Session) -> list[int]:
    return sorted((a for (a,) in db.execute(select(distinct(CompraCentralizada.anio))).all()), reverse=True)


def listar_compra(db: Session, anio: int) -> list[dict]:
    return [
        _a_dict(c)
        for c in db.scalars(select(CompraCentralizada).where(CompraCentralizada.anio == anio))
    ]


def mapa_compra(db: Session, anio: int) -> dict[str, dict]:
    """Código SISMED (= producto.medcod) → registro de compra, para el cruce."""
    return {
        c.codigo_sismed: _a_dict(c)
        for c in db.scalars(select(CompraCentralizada).where(CompraCentralizada.anio == anio))
    }


def mapa_edicion(db: Session, anio: int) -> dict[str, dict[str, str | None]]:
    """codigo_sismed → {campo: valor editado por el doc}."""
    mapa: dict[str, dict[str, str | None]] = {}
    for e in db.scalars(select(CompraEdicion).where(CompraEdicion.anio == anio)):
        mapa.setdefault(e.codigo_sismed, {})[e.campo] = e.valor
    return mapa


def guardar_edicion(db: Session, anio: int, codigo_sismed: str, campo: str, valor: str | None) -> None:
    stmt = mysql_insert(CompraEdicion).values(
        anio=anio, codigo_sismed=codigo_sismed, campo=campo, valor=valor
    )
    db.execute(stmt.on_duplicate_key_update(valor=stmt.inserted.valor, editado_en=func.now()))
    db.commit()


def revertir_edicion(db: Session, anio: int, codigo_sismed: str, campo: str) -> None:
    """Quita la edición → vuelve a mostrarse el valor del archivo."""
    db.execute(
        delete(CompraEdicion).where(
            CompraEdicion.anio == anio,
            CompraEdicion.codigo_sismed == codigo_sismed,
            CompraEdicion.campo == campo,
        )
    )
    db.commit()
