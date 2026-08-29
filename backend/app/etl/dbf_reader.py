"""Lector de DBF — usa el encoding que el propio archivo declara."""
from pathlib import Path

from dbfread import DBF

from app.core.config import get_settings


def leer_dbf(ruta: str | Path) -> list[dict]:
    """
    Lee un DBF completo. El header dBase/FoxPro trae un byte de "language
    driver" que declara el codepage real del archivo (verificado: nuestros
    DBF traen 0x03 = Windows ANSI/cp1252, no cp850 — forzar cp850 antes
    decodía silenciosamente tildes y ñ como caracteres de dibujo de cajas,
    sin lanzar error, porque cp850 nunca falla con ningún byte).

    Por eso NO se fuerza un encoding: se deja que dbfread lo detecte del
    header. `dbf_encodings` (config) solo se prueba como último recurso,
    si ese autodetectado falla (header corrupto o ausente).
    """
    ruta = Path(ruta)
    try:
        tabla = DBF(str(ruta), char_decode_errors="strict", lowernames=True)
        return [dict(registro) for registro in tabla]
    except UnicodeDecodeError as exc_autodetectado:
        errores = [f"autodetectado: {exc_autodetectado}"]

    for encoding in get_settings().dbf_encodings:
        try:
            tabla = DBF(str(ruta), encoding=encoding, char_decode_errors="strict", lowernames=True)
            return [dict(registro) for registro in tabla]
        except UnicodeDecodeError as exc:
            errores.append(f"{encoding}: {exc}")
    raise ValueError(
        f"No se pudo leer {ruta.name} con el encoding autodetectado ni con "
        f"{get_settings().dbf_encodings}: {'; '.join(errores)}"
    )
