"""POST /api/asistente — asistente de consultas local por reglas. Reconoce la
intención de la pregunta, llama a los repositorios ya existentes y redacta la
respuesta con datos reales. Sin LLM, sin servicios externos. Ver
app/services/asistente.py."""
import html
from datetime import datetime

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.repositories.asistente_repository import agrupadas, reformulaciones
from app.services.asistente import responder

router = APIRouter(prefix="/api/asistente", tags=["asistente"])


class AsistentePregunta(BaseModel):
    pregunta: str
    sesion_id: str | None = None


class DatosTabla(BaseModel):
    columnas: list[str]
    filas: list[list[str]]
    total: int


class EnlaceModulo(BaseModel):
    pagina: str
    filtros: dict = {}


class AsistenteRespuesta(BaseModel):
    intencion_detectada: str
    respuesta_texto: str
    datos: DatosTabla
    sugerencias: list[str]
    enlace: EnlaceModulo | None = None


@router.post("", response_model=AsistenteRespuesta)
def preguntar(payload: AsistentePregunta, db: Session = Depends(get_db)) -> AsistenteRespuesta:
    return AsistenteRespuesta(**responder(db, payload.pregunta, sesion_id=payload.sesion_id))


def _fecha(d) -> str:
    return d.strftime("%d/%m/%Y %H:%M") if isinstance(d, datetime) else "—"


@router.get("/no-reconocidas", response_class=HTMLResponse)
def vista_no_reconocidas(db: Session = Depends(get_db)) -> str:
    """Vista simple (para el desarrollador) de las preguntas que el asistente NO
    reconoció — la fuente real para enseñarle cómo escribe el doc. Agrupadas por
    frecuencia, más las reformulaciones detectadas (lo que el doc quería decir)."""
    grupos = agrupadas(db)
    reforms = reformulaciones(db)
    e = html.escape

    filas_grupos = "".join(
        f"<tr><td class='n'>{g['veces']}</td><td>{e(g['ejemplo'] or g['normalizado'])}</td>"
        f"<td class='muted'>{e(g['normalizado'])}</td><td class='muted'>{_fecha(g['ultima'])}</td></tr>"
        for g in grupos
    ) or "<tr><td colspan='4' class='muted'>Nada por ahora. Cuando el doc use el chat y algo no se entienda, aparecerá aquí.</td></tr>"

    filas_reform = "".join(
        f"<tr><td>{e(r['texto'])}</td><td>→</td><td>{e(r['reformulacion'] or '')}</td>"
        f"<td><span class='tag'>{e(r['intencion'] or '')}</span></td><td class='muted'>{_fecha(r['creado'])}</td></tr>"
        for r in reforms
    ) or "<tr><td colspan='5' class='muted'>Sin reformulaciones detectadas todavía.</td></tr>"

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<title>Asistente · preguntas no reconocidas</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
 body{{font-family:system-ui,Segoe UI,Roboto,sans-serif;margin:24px;color:#212529;background:#f8f9fa}}
 h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:2rem}}
 p.hint{{color:#6c757d;max-width:60rem}}
 table{{border-collapse:collapse;width:100%;background:#fff;box-shadow:0 1px 3px rgba(0,0,0,.08);border-radius:6px;overflow:hidden}}
 th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #eee;font-size:.9rem;vertical-align:top}}
 th{{background:#212529;color:#fff;font-weight:600}}
 td.n{{font-weight:700;text-align:right;width:3rem}}
 .muted{{color:#868e96;font-size:.82rem}}
 .tag{{background:#e7f1ff;color:#0d6efd;border:1px solid #b6d4fe;border-radius:4px;padding:1px 6px;font-size:.8rem}}
</style></head><body>
<h1>Asistente · preguntas no reconocidas</h1>
<p class="hint">Esta es la fuente real para enseñarle al asistente cómo escribe el doc: no frases inventadas,
sino las que él realmente escribió y no se entendieron. Revisa las más frecuentes y añade sus variantes al
diccionario <code>INTENCIONES</code> en <code>app/services/asistente.py</code>.</p>

<h2>No reconocidas (agrupadas, más frecuentes primero)</h2>
<table><thead><tr><th>Veces</th><th>Ejemplo (tal cual)</th><th>Normalizado</th><th>Última vez</th></tr></thead>
<tbody>{filas_grupos}</tbody></table>

<h2>Reformulaciones detectadas — lo que el doc quería decir</h2>
<p class="hint">El doc preguntó algo que no se entendió y, en la misma sesión, reformuló y sí funcionó.
Ese par revela la intención tras su frase: candidatos directos para el diccionario.</p>
<table><thead><tr><th>Escribió (no se entendió)</th><th></th><th>Reformuló</th><th>Intención</th><th>Cuándo</th></tr></thead>
<tbody>{filas_reform}</tbody></table>
</body></html>"""
