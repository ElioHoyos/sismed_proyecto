"""
Importador del catálogo OFICIAL del almacén — SISMED: MPRODUCTO.DBF.

Es un UPSERT por medcod, no un reemplazo: los productos que ya existían (creados
parcialmente desde los ICI, solo con medcod + nombre) se enriquecen con los
campos oficiales; los nuevos se crean; ninguno se borra ni se duplica.

Encoding: se deja que `leer_dbf` lo autodetecte del header (resulta cp1252 y
decodifica bien las tildes). NO se fuerza cp850 — en este archivo corrompería
los acentos (UNGÜENTO → UNG▄ENTO), igual que pasaba con los ICI.

Marca `producto.origen`:
  "MPRODUCTO" → está en el catálogo oficial.
  "ICI"       → productos que solo aparecen en los ICI de establecimientos y no
                en el catálogo oficial; se conservan tal cual (con lo que trae el
                ICI) para poder listarlos aparte, no se borran.
"""
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.etl.dbf_reader import leer_dbf
from app.models.producto import Producto

ORIGEN_OFICIAL = "MPRODUCTO"
ORIGEN_ICI = "ICI"


@dataclass
class ResumenMProducto:
    filas_leidas: int = 0
    creados: int = 0
    actualizados: int = 0
    marcados_solo_ici: int = 0


def _texto(valor) -> str | None:
    if valor is None:
        return None
    t = str(valor).strip()
    return t or None


def _entero(valor) -> int | None:
    if valor is None or valor == "":
        return None
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return None


def _fijar(producto: Producto, atributo: str, valor) -> None:
    """Asigna solo si hay valor (no pisa datos existentes con vacío)."""
    if valor is not None:
        setattr(producto, atributo, valor)


def importar_mproducto(db: Session, ruta_dbf: str | Path) -> ResumenMProducto:
    ruta_dbf = Path(ruta_dbf)
    resumen = ResumenMProducto()

    filas = leer_dbf(ruta_dbf)
    resumen.filas_leidas = len(filas)

    productos = {p.medcod: p for p in db.scalars(select(Producto))}

    for fila in filas:
        medcod = _texto(fila.get("medcod"))
        if medcod is None:
            continue

        nombre = _texto(fila.get("mednom"))
        medpet = _texto(fila.get("medpet"))
        narcotico = _texto(fila.get("mednarcot")) or _texto(fila.get("mnarcot"))

        producto = productos.get(medcod)
        creado = producto is None
        if creado:
            producto = Producto(medcod=medcod, nombre=nombre or medcod)
            db.add(producto)
            productos[medcod] = producto

        # Campos de texto (solo si vienen con valor, para no borrar lo existente)
        _fijar(producto, "nombre", nombre)
        _fijar(producto, "nombre_abrev", _texto(fila.get("mednomabr")))
        _fijar(producto, "concentracion", _texto(fila.get("medcnc")))
        _fijar(producto, "forma_farma", _texto(fila.get("medff")))
        _fijar(producto, "presentacion", _texto(fila.get("medpres")))
        _fijar(producto, "tipo", (_texto(fila.get("medtip")) or "").upper() or None)
        _fijar(producto, "medest", (_texto(fila.get("medest")) or "").upper() or None)
        _fijar(producto, "codigo_siga", _texto(fila.get("codigo_sig")))
        _fijar(producto, "reg_sanitario", _texto(fila.get("medregsan")))
        _fijar(producto, "stock_min", _entero(fila.get("prdstkmin")))
        _fijar(producto, "stock_max", _entero(fila.get("prdstkmax")))
        _fijar(producto, "punto_reposicion", _entero(fila.get("prdptorep")))

        # MEDPET crudo + derivado; MEDNARCOT no vacío ⇒ controlado (catálogo oficial: definitivo)
        if medpet is not None:
            producto.medpet = medpet
            producto.es_petitorio = medpet.upper() == "P"
        producto.controlado = bool(narcotico)
        producto.origen = ORIGEN_OFICIAL

        if creado:
            resumen.creados += 1
        else:
            resumen.actualizados += 1

    db.flush()

    # Lo que quedó sin origen viene solo de los ICI (no está en el catálogo
    # oficial): se marca ICI para poder listarlo, no se borra.
    resultado = db.execute(
        update(Producto).where(Producto.origen.is_(None)).values(origen=ORIGEN_ICI)
    )
    resumen.marcados_solo_ici = resultado.rowcount or 0

    db.commit()
    return resumen


def main() -> None:
    import sys

    ruta = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app/data/MPRODUCTO.DBF")
    db = SessionLocal()
    try:
        r = importar_mproducto(db, ruta)
    finally:
        db.close()

    print(f"MPRODUCTO: {ruta}")
    print(f"  filas leídas:        {r.filas_leidas}")
    print(f"  productos creados:   {r.creados}")
    print(f"  productos actualizados: {r.actualizados}")
    print(f"  marcados solo_ici:   {r.marcados_solo_ici}")


if __name__ == "__main__":
    main()
