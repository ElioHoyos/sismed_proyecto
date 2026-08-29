"""Estado de la compra centralizada (CENARES) para el cruce con Disponibilidad.
El front lo trae por año y lo cruza por Código SISMED = producto.medcod."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.compra_repository import (
    CAMPOS_EDITABLES,
    anios_disponibles,
    guardar_edicion,
    listar_compra,
    revertir_edicion,
)

router = APIRouter(prefix="/api/compra-centralizada", tags=["compra-centralizada"])


class CompraRegistroOut(BaseModel):
    codigo_sismed: str
    codigo_siga: str | None
    tipo_producto: str | None
    procedimiento: str | None
    estado_situacion: str | None
    observacion_estado: str | None
    reg_siga_situacion: str | None
    reg_siga_observacion: str | None
    contratista: str | None
    nro_contrato: str | None
    fecha_convocatoria: str | None
    fecha_buena_pro: str | None
    fecha_entrega: str | None
    fecha_entrega_texto: str | None
    observacion: str | None


class CompraOut(BaseModel):
    anio: int | None
    anios_disponibles: list[int]
    total: int
    registros: list[CompraRegistroOut]


def _iso(d) -> str | None:
    return d.isoformat() if isinstance(d, date) else None


@router.get("", response_model=CompraOut)
def obtener_compra(
    anio: int | None = Query(None, description="Año de la compra; por defecto el más reciente cargado"),
    db: Session = Depends(get_db),
) -> CompraOut:
    anios = anios_disponibles(db)
    if anio is None:
        anio = anios[0] if anios else None
    filas = listar_compra(db, anio) if anio is not None else []
    registros = [
        CompraRegistroOut(
            **{
                **f,
                "fecha_convocatoria": _iso(f["fecha_convocatoria"]),
                "fecha_buena_pro": _iso(f["fecha_buena_pro"]),
                "fecha_entrega": _iso(f["fecha_entrega"]),
            }
        )
        for f in filas
    ]
    return CompraOut(anio=anio, anios_disponibles=anios, total=len(registros), registros=registros)


class EdicionIn(BaseModel):
    anio: int
    codigo_sismed: str
    campo: str
    valor: str | None = None


@router.put("/edicion")
def editar(payload: EdicionIn, db: Session = Depends(get_db)) -> dict:
    """Guarda la edición del doc sobre un campo (aparte del valor del archivo)."""
    if payload.campo not in CAMPOS_EDITABLES:
        raise HTTPException(400, f"campo no editable: {payload.campo!r}")
    guardar_edicion(db, payload.anio, payload.codigo_sismed.zfill(5), payload.campo, payload.valor)
    return {"ok": True}


@router.delete("/edicion")
def revertir(
    anio: int = Query(...),
    codigo_sismed: str = Query(...),
    campo: str = Query(...),
    db: Session = Depends(get_db),
) -> dict:
    """Quita la edición → vuelve el valor del archivo."""
    revertir_edicion(db, anio, codigo_sismed.zfill(5), campo)
    return {"ok": True}
