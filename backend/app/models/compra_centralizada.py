"""Estado de la compra centralizada de CENARES (fuente: el XLSX que le llega al
doc periódicamente). Una fila por (año, código SISMED). Ver app/etl/cenares.py."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, SmallInteger, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class CompraCentralizada(Base):
    __tablename__ = "compra_centralizada"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    anio: Mapped[int] = mapped_column(SmallInteger)  # 2025 / 2026 (de la hoja)
    codigo_sismed: Mapped[str] = mapped_column(String(20))  # col B, zfill(5) — llave de cruce
    codigo_siga: Mapped[str | None] = mapped_column(String(20))  # col C — cruce alternativo

    tipo_producto: Mapped[str | None] = mapped_column(String(60))  # E
    procedimiento: Mapped[str | None] = mapped_column(String(255))  # F
    estado_situacion: Mapped[str | None] = mapped_column(String(80))  # G (Situación)
    observacion_estado: Mapped[str | None] = mapped_column(Text)  # H
    reg_siga_situacion: Mapped[str | None] = mapped_column(String(120))  # I (Situación)
    reg_siga_observacion: Mapped[str | None] = mapped_column(Text)  # J
    contratista: Mapped[str | None] = mapped_column(String(255))  # K
    nro_contrato: Mapped[str | None] = mapped_column(String(60))  # L
    fecha_convocatoria: Mapped[date | None] = mapped_column(Date)  # M
    fecha_buena_pro: Mapped[date | None] = mapped_column(Date)  # N
    fecha_entrega: Mapped[date | None] = mapped_column(Date)  # O parseada (si es fecha real)
    fecha_entrega_texto: Mapped[str | None] = mapped_column(String(120))  # O tal cual (ej. "NOVIEMBRE 2026")
    observacion: Mapped[str | None] = mapped_column(Text)  # P

    importado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class CompraEdicion(Base):
    """Ediciones del doc sobre campos de CENARES, guardadas APARTE del valor del
    archivo (una fila por campo editado). Sobreviven a la reimportación: al
    reimportar solo se reemplaza `compra_centralizada`; estas ediciones quedan y
    ganan sobre el valor del archivo. Presencia de la fila = campo editado."""
    __tablename__ = "compra_edicion"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    anio: Mapped[int] = mapped_column(SmallInteger)
    codigo_sismed: Mapped[str] = mapped_column(String(20))
    campo: Mapped[str] = mapped_column(String(40))  # observacion, fecha_entrega_texto, ...
    valor: Mapped[str | None] = mapped_column(Text)
    editado_en: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
