"""Consultas sobre el estado de las importaciones — qué establecimientos faltan."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.establecimiento import Establecimiento
from app.models.importacion import Importacion


def listar_pendientes(db: Session, periodo: date) -> dict:
    activos = db.scalars(
        select(Establecimiento)
        .where(Establecimiento.activo, Establecimiento.es_almacen.is_(False))
        .order_by(Establecimiento.nombre)
    ).all()

    cargados_cod = set(
        db.scalars(
            select(Importacion.establecimiento_cod).where(
                Importacion.periodo == periodo, Importacion.estado == "OK"
            )
        ).all()
    )

    faltantes = [e for e in activos if e.cod_2000 not in cargados_cod]

    return {
        "periodo": periodo,
        "total_establecimientos": len(activos),
        "cargados": len(activos) - len(faltantes),
        "faltantes": [{"cod_2000": e.cod_2000, "nombre": e.nombre} for e in faltantes],
    }
