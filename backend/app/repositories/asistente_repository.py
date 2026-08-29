"""Registro y lectura de las preguntas no reconocidas del asistente. Es el
mecanismo de aprendizaje: se guarda lo que el doc escribió y no se entendió, y
cuando reformula y sí se entiende, se liga como reformulación."""
from datetime import datetime, timedelta

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.models.consulta_no_reconocida import ConsultaNoReconocida

# Ventana para considerar que una pregunta reconocida es reformulación de una
# no reconocida anterior de la misma sesión.
VENTANA_REFORMULACION = timedelta(hours=1)


def registrar_no_reconocida(
    db: Session,
    texto: str,
    normalizado: str,
    sesion_id: str | None,
    intenciones_sugeridas: list[str] | None = None,
) -> None:
    db.add(
        ConsultaNoReconocida(
            sesion_id=sesion_id,
            texto=texto,
            normalizado=normalizado,
            intenciones_sugeridas=", ".join(intenciones_sugeridas) if intenciones_sugeridas else None,
        )
    )
    db.commit()


def marcar_reformulacion(db: Session, sesion_id: str | None, texto: str, intencion: str) -> None:
    """Si en esta sesión hubo una pregunta no reconocida reciente sin reformular,
    la liga a esta pregunta (que sí se entendió): el mapeo real de lo que el doc
    quería decir."""
    if not sesion_id:
        return
    previa = db.scalar(
        select(ConsultaNoReconocida)
        .where(
            ConsultaNoReconocida.sesion_id == sesion_id,
            ConsultaNoReconocida.reformulada.is_(False),
        )
        .order_by(desc(ConsultaNoReconocida.creado))
        .limit(1)
    )
    if previa is None or previa.creado is None:
        return
    if datetime.now() - previa.creado > VENTANA_REFORMULACION:
        return
    previa.reformulada = True
    previa.reformulacion_texto = texto
    previa.reformulacion_intencion = intencion
    db.commit()


def agrupadas(db: Session, limite: int = 200) -> list[dict]:
    """Preguntas no reconocidas agrupadas por texto normalizado, más frecuentes
    primero — la lista de qué frases enseñarle al asistente."""
    filas = db.execute(
        select(
            ConsultaNoReconocida.normalizado,
            func.count().label("veces"),
            func.max(ConsultaNoReconocida.creado).label("ultima"),
            func.max(ConsultaNoReconocida.texto).label("ejemplo"),
        )
        .group_by(ConsultaNoReconocida.normalizado)
        .order_by(desc("veces"), desc("ultima"))
        .limit(limite)
    ).all()
    return [
        {"normalizado": n or "", "veces": v, "ultima": u, "ejemplo": e}
        for n, v, u, e in filas
    ]


def reformulaciones(db: Session, limite: int = 200) -> list[dict]:
    """Pares 'lo que escribió (no se entendió)' → 'reformulación (intención)'.
    Lo más valioso: revela cómo el doc nombra cada intención."""
    filas = db.scalars(
        select(ConsultaNoReconocida)
        .where(ConsultaNoReconocida.reformulada.is_(True))
        .order_by(desc(ConsultaNoReconocida.creado))
        .limit(limite)
    ).all()
    return [
        {
            "texto": c.texto,
            "reformulacion": c.reformulacion_texto,
            "intencion": c.reformulacion_intencion,
            "creado": c.creado,
        }
        for c in filas
    ]
