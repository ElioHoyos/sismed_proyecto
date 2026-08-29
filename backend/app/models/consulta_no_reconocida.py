"""Registro de preguntas que el asistente NO reconoció (cayó en 'no entendí' o
'¿quisiste decir?'). Es la fuente real para enseñarle cómo escribe el doc: se
revisa con uso real y se enriquece el diccionario de sinónimos del asistente.

`reformulada` se marca cuando, en la misma sesión, el doc volvió a preguntar y
esa segunda pregunta SÍ se reconoció — así queda el mapeo real 'lo que escribió
mal' → 'la intención que quería'. Ver app/services/asistente.py."""
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class ConsultaNoReconocida(Base):
    __tablename__ = "consultas_no_reconocidas"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sesion_id: Mapped[str | None] = mapped_column(String(40))  # para ligar reformulaciones
    texto: Mapped[str] = mapped_column(Text)  # tal cual lo escribió el doc
    normalizado: Mapped[str | None] = mapped_column(String(255))  # normalizado (para agrupar)
    # Si fue "¿quisiste decir?", las intenciones cercanas que se sugirieron.
    intenciones_sugeridas: Mapped[str | None] = mapped_column(String(255))
    creado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # Reformulación: el doc volvió a preguntar y esa sí se entendió.
    reformulada: Mapped[bool] = mapped_column(Boolean, default=False)
    reformulacion_texto: Mapped[str | None] = mapped_column(Text)
    reformulacion_intencion: Mapped[str | None] = mapped_column(String(40))
    revisada: Mapped[bool] = mapped_column(Boolean, default=False)  # el dev ya la revisó
