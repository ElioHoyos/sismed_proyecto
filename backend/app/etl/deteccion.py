"""
Detección del establecimiento a partir del NOMBRE del archivo DBF.

El DBF del ICI no trae el código de establecimiento adentro (CODIGO_PRE
llega vacío), así que hay que inferirlo del nombre del archivo cruzándolo
contra `establecimiento.nombre`. El cruce NO puede ser substring exacto:
el archivo suele traer solo un fragmento del nombre oficial —el caso
canónico es "C.S MICAELA" → "MICAELA BASTIDAS", donde ni el nombre del
archivo contiene al del establecimiento ni al revés—.

Se compara por *tokens* (palabras significativas) con similitud difusa y
se reporta un nivel de confianza para que la UI pida confirmación cuando
la detección no sea contundente:

    alta          → todos los tokens del archivo explicados por UN
                    establecimiento, y con margen claro sobre el segundo.
    dudosa        → hay coincidencia parcial, o dos establecimientos
                    empatan (p. ej. "SAN FERNANDO" vs "SAN FERNANDO II").
    no_encontrado → nada coincide de forma razonable.
"""
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

CONFIANZA_ALTA = "alta"
CONFIANZA_DUDOSA = "dudosa"
CONFIANZA_NO_ENCONTRADO = "no_encontrado"

# Palabras que no identifican: tipo de establecimiento, conectores, relleno.
_STOPWORDS = frozenset({
    "CS", "PS", "C", "S", "P", "EESS", "IPRESS",
    "DE", "DEL", "LA", "EL", "LOS", "LAS", "Y", "EN",
    "CENTRO", "PUESTO", "SALUD", "ESTABLECIMIENTO",
})

# Umbrales de decisión (ver docstring del módulo).
_MIN_COBERTURA_DUDOSA = 0.5
_MIN_MARGEN_ALTA = 0.2
_SIMILITUD_TOKEN = 0.86


@dataclass
class Candidato:
    cod_2000: str
    nombre: str
    score: float


@dataclass
class ResultadoDeteccion:
    """`establecimiento` es el mejor candidato (None si no_encontrado);
    `candidatos` son los mejores para ofrecerlos en la corrección manual."""
    confianza: str
    establecimiento: Candidato | None
    candidatos: list[Candidato]


def _sin_acentos(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", texto)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def _tokens(texto: str) -> list[str]:
    limpio = _sin_acentos(texto).upper()
    crudos = re.split(r"[^A-Z0-9]+", limpio)
    return [t for t in crudos if t and t not in _STOPWORDS]


def _tokens_coinciden(a: str, b: str) -> bool:
    """Igualdad difusa entre dos palabras: exacta, prefijo compartido
    (MICAELA ~ MICAELAB…) o alta similitud (tolera errores de tipeo)."""
    if a == b:
        return True
    if len(a) >= 4 and len(b) >= 4 and (a.startswith(b) or b.startswith(a)):
        return True
    return SequenceMatcher(None, a, b).ratio() >= _SIMILITUD_TOKEN


def _puntuar(file_tokens: list[str], est_tokens: list[str]) -> tuple[float, float]:
    """Devuelve (score, cobertura_archivo).

    cobertura_archivo = fracción de tokens del ARCHIVO explicados por el
    establecimiento — es la señal principal ("¿el nombre del archivo cabe
    dentro de este establecimiento?"). El score suma un pequeño premio por
    cobertura del establecimiento para desempatar hacia el nombre más
    ajustado (MICAELA explica 100% del archivo y 50% de "MICAELA BASTIDAS";
    "MICAELA BASTIDAS" le gana a "MICAELA BASTIDAS SECTOR 2")."""
    if not file_tokens or not est_tokens:
        return 0.0, 0.0
    emparejados = sum(
        1 for ft in file_tokens if any(_tokens_coinciden(ft, et) for et in est_tokens)
    )
    if not emparejados:
        return 0.0, 0.0
    cobertura_archivo = emparejados / len(file_tokens)
    cobertura_est = emparejados / len(est_tokens)
    return cobertura_archivo + 0.3 * cobertura_est, cobertura_archivo


def coincide_nombre(
    nombre_archivo: str,
    nombre_establecimiento: str,
    umbral: float = _MIN_COBERTURA_DUDOSA,
) -> bool:
    """Chequeo de sanidad tolerante: ¿el nombre del archivo es plausible para
    este establecimiento? Usa la misma lógica de tokens que la detección, para
    que un archivo correctamente resuelto ("C.S MICAELA" → "MICAELA BASTIDAS")
    no dispare una incidencia falsa. Sin tokens útiles → no molesta (True)."""
    file_tokens = _tokens(Path(nombre_archivo).stem)
    est_tokens = _tokens(nombre_establecimiento)
    if not file_tokens or not est_tokens:
        return True
    _, cobertura_archivo = _puntuar(file_tokens, est_tokens)
    return cobertura_archivo >= umbral


def detectar_establecimiento(
    nombre_archivo: str,
    catalogo: list[tuple[str, str]],
    top: int = 3,
) -> ResultadoDeteccion:
    """`catalogo`: lista de (cod_2000, nombre) de los establecimientos activos."""
    file_tokens = _tokens(Path(nombre_archivo).stem)

    puntuados: list[tuple[float, float, str, str]] = []
    for cod, nombre in catalogo:
        score, cobertura_archivo = _puntuar(file_tokens, _tokens(nombre))
        if score > 0:
            puntuados.append((score, cobertura_archivo, cod, nombre))

    puntuados.sort(key=lambda x: x[0], reverse=True)
    candidatos = [Candidato(cod_2000=c, nombre=n, score=round(s, 3)) for s, _, c, n in puntuados[:top]]

    if not puntuados:
        return ResultadoDeteccion(CONFIANZA_NO_ENCONTRADO, None, [])

    mejor_score, mejor_cobertura, mejor_cod, mejor_nombre = puntuados[0]
    segundo_score = puntuados[1][0] if len(puntuados) > 1 else 0.0
    mejor = Candidato(cod_2000=mejor_cod, nombre=mejor_nombre, score=round(mejor_score, 3))

    if mejor_cobertura >= 0.999 and (mejor_score - segundo_score) >= _MIN_MARGEN_ALTA:
        return ResultadoDeteccion(CONFIANZA_ALTA, mejor, candidatos)
    if mejor_cobertura >= _MIN_COBERTURA_DUDOSA:
        return ResultadoDeteccion(CONFIANZA_DUDOSA, mejor, candidatos)
    return ResultadoDeteccion(CONFIANZA_NO_ENCONTRADO, None, candidatos)
