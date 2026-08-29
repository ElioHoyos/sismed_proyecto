"""
Materializa las subidas del ICI a disco: acepta DBF sueltos o un ZIP con
varios DBF adentro (para el cierre mensual completo, ~89 establecimientos)
y devuelve una lista plana de (nombre_basename, ruta_en_disco) lista para
procesar igual que si cada archivo hubiera venido suelto.

RAR NO se soporta a propósito: descomprimirlo necesita dependencias
externas frágiles (unrar), mientras que ZIP es nativo en Python (zipfile).
Si llega un .rar se rechaza pidiendo ZIP.
"""
import zipfile
from pathlib import Path

from fastapi import UploadFile


class ArchivoNoSoportado(ValueError):
    """Subida inválida (formato no admitido, ZIP dañado, sin DBF). El endpoint
    la traduce a HTTP 400 con este mensaje, apto para mostrar al usuario."""


def _es_artefacto_mac(nombre_interno: str) -> bool:
    """Los ZIP hechos en macOS traen basura (__MACOSX/, ._nombre) que no es
    un DBF real."""
    return nombre_interno.startswith("__MACOSX") or Path(nombre_interno).name.startswith("._")


def _extension(nombre: str) -> str:
    return nombre.lower().rsplit(".", 1)[-1] if "." in nombre else ""


def _expandir_zip(ruta_zip: Path, destino_dir: Path) -> list[tuple[str, Path]]:
    """Extrae los .dbf del ZIP a `destino_dir`, cada uno en su subcarpeta para
    conservar el nombre real sin colisiones. Escribe solo por *basename* en un
    directorio controlado → inmune a zip-slip (rutas ../ en el ZIP)."""
    salida: list[tuple[str, Path]] = []
    try:
        with zipfile.ZipFile(ruta_zip) as zf:
            for j, info in enumerate(zf.infolist()):
                if info.is_dir() or _es_artefacto_mac(info.filename):
                    continue
                if _extension(info.filename) not in ("dbf", "xlsx"):
                    continue
                base_nombre = Path(info.filename).name
                sub = destino_dir / f"e{j}"
                sub.mkdir(parents=True, exist_ok=True)
                destino = sub / base_nombre
                with zf.open(info) as origen:
                    destino.write_bytes(origen.read())
                salida.append((base_nombre, destino))
    except zipfile.BadZipFile:
        raise ArchivoNoSoportado(f"'{ruta_zip.name}' no es un ZIP válido o está dañado.")
    return salida


async def materializar_dbfs(
    archivos: list[UploadFile],
    directorio_tmp: str | Path,
) -> list[tuple[str, Path]]:
    """Escribe las subidas en `directorio_tmp` y devuelve (basename, ruta) por
    cada DBF, expandiendo los ZIP. Dedup por basename (se queda con el primero)
    para que previsualización e importación vean exactamente la misma lista.

    Lanza ArchivoNoSoportado si hay un .rar, un formato desconocido, un ZIP
    dañado, o si al final no hubo ningún DBF."""
    base = Path(directorio_tmp)
    resultado: list[tuple[str, Path]] = []
    vistos: set[str] = set()

    def _agregar(nombre: str, ruta: Path) -> None:
        if nombre in vistos:
            return
        vistos.add(nombre)
        resultado.append((nombre, ruta))

    for i, archivo in enumerate(archivos):
        nombre = Path(archivo.filename or "archivo").name
        ext = _extension(nombre)
        destino_dir = base / str(i)
        destino_dir.mkdir(parents=True, exist_ok=True)
        contenido = await archivo.read()

        if ext == "rar":
            raise ArchivoNoSoportado(
                f"'{nombre}' es un archivo .rar y no se admite. Solo se aceptan "
                "archivos .dbf o .xlsx sueltos, o un .zip con ellos adentro. Vuelve "
                "a comprimir en formato ZIP."
            )
        if ext == "zip":
            ruta_zip = destino_dir / nombre
            ruta_zip.write_bytes(contenido)
            for base_nombre, ruta in _expandir_zip(ruta_zip, destino_dir):
                _agregar(base_nombre, ruta)
            continue
        if ext in ("dbf", "xlsx"):
            destino = destino_dir / nombre
            destino.write_bytes(contenido)
            _agregar(nombre, destino)
            continue

        raise ArchivoNoSoportado(
            f"'{nombre}' no es un formato admitido. Solo se aceptan archivos .dbf, "
            ".xlsx (compra CENARES) o un .zip con esos archivos adentro."
        )

    if not resultado:
        raise ArchivoNoSoportado(
            "No se encontró ningún archivo .dbf ni .xlsx para procesar (¿el ZIP venía vacío?)."
        )
    return resultado
