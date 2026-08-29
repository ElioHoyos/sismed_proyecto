"""
Backfill de la clasificación del catálogo `producto` (MEDTIP, MEDPET, MEDEST,
FF) a partir de los DBF del ICI. Es una migración de una sola vez: el catálogo
histórico solo tenía medcod + nombre; estos códigos ya venían en cada DBF.

De aquí en adelante el importador (app/etl/ici.py) mantiene estos campos al día
en cada carga, así que este script normalmente se corre una vez.

Uso:
    python -m app.etl.backfill_clasificacion            # lee app/data/*.DBF
    python -m app.etl.backfill_clasificacion RUTA_DIR   # otra carpeta de DBF
"""
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.etl.dbf_reader import leer_dbf
from app.models.producto import Producto

RUTA_DBF_DEFECTO = Path("app/data")


def _clasificacion_desde_dbfs(directorio: Path) -> dict[str, dict[str, str]]:
    """medcod → {tipo, medpet, medest, forma_farma}, uniendo todos los DBF del
    directorio. Estos códigos son atributos del PRODUCTO (iguales en todos los
    establecimientos), así que basta con verlos en cualquier DBF que lo liste;
    un valor no vacío rellena huecos dejados por otro archivo."""
    por_medcod: dict[str, dict[str, str]] = {}
    archivos = sorted(p for p in directorio.iterdir() if p.suffix.lower() == ".dbf")
    for dbf in archivos:
        for fila in leer_dbf(dbf):
            medcod = (fila.get("codigo_med") or "").strip()
            if not medcod:
                continue
            destino = por_medcod.setdefault(medcod, {})
            crudos = {
                "tipo": (fila.get("medtip") or "").strip().upper(),
                "medpet": (fila.get("medpet") or "").strip(),
                "medest": (fila.get("medest") or "").strip().upper(),
                "forma_farma": (fila.get("ff") or "").strip(),
            }
            for campo, valor in crudos.items():
                if valor and not destino.get(campo):
                    destino[campo] = valor
    return por_medcod


def backfill(db: Session, directorio: Path = RUTA_DBF_DEFECTO) -> dict:
    clasif = _clasificacion_desde_dbfs(directorio)

    productos = db.scalars(select(Producto)).all()
    total = len(productos)
    actualizados = 0
    for producto in productos:
        datos = clasif.get(producto.medcod)
        if not datos:
            continue
        if "tipo" in datos:
            producto.tipo = datos["tipo"]
        if "medpet" in datos:
            producto.medpet = datos["medpet"]
            producto.es_petitorio = datos["medpet"].upper() == "P"
        if "medest" in datos:
            producto.medest = datos["medest"]
        if "forma_farma" in datos:
            producto.forma_farma = datos["forma_farma"]
        actualizados += 1

    db.commit()

    con_tipo = db.scalar(select(func.count()).select_from(Producto).where(Producto.tipo.isnot(None)))
    con_medpet = db.scalar(select(func.count()).select_from(Producto).where(Producto.medpet.isnot(None)))
    con_medest = db.scalar(select(func.count()).select_from(Producto).where(Producto.medest.isnot(None)))
    con_ff = db.scalar(select(func.count()).select_from(Producto).where(Producto.forma_farma.isnot(None)))
    return {
        "medcods_en_dbfs": len(clasif),
        "productos_total": total,
        "productos_actualizados": actualizados,
        "con_medtip": con_tipo,
        "con_medpet": con_medpet,
        "con_medest": con_medest,
        "con_ff": con_ff,
    }


def main() -> None:
    import sys

    directorio = Path(sys.argv[1]) if len(sys.argv) > 1 else RUTA_DBF_DEFECTO
    db = SessionLocal()
    try:
        resumen = backfill(db, directorio)
    finally:
        db.close()

    print(f"DBF leídos de: {directorio}")
    print(f"  medcods distintos en los DBF:      {resumen['medcods_en_dbfs']}")
    print(f"  productos en catálogo:             {resumen['productos_total']}")
    print(f"  productos actualizados:            {resumen['productos_actualizados']}")
    print(f"  con MEDTIP (tipo):                 {resumen['con_medtip']}/{resumen['productos_total']}")
    print(f"  con MEDPET:                        {resumen['con_medpet']}/{resumen['productos_total']}")
    print(f"  con MEDEST:                        {resumen['con_medest']}/{resumen['productos_total']}")
    print(f"  con FF (forma_farma):              {resumen['con_ff']}/{resumen['productos_total']}")


if __name__ == "__main__":
    main()
