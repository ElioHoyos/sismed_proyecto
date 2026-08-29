"""Catálogo de productos (SISMED: mproducto)."""
from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Producto(Base):
    __tablename__ = "producto"

    id: Mapped[int] = mapped_column(primary_key=True)
    medcod: Mapped[str] = mapped_column(String(20), unique=True)
    codigo_siga: Mapped[str | None] = mapped_column(String(20))  # MPRODUCTO: CODIGO_SIG
    nombre: Mapped[str] = mapped_column(String(200))
    nombre_abrev: Mapped[str | None] = mapped_column(String(100))
    presentacion: Mapped[str | None] = mapped_column(String(100))
    concentracion: Mapped[str | None] = mapped_column(String(60))
    forma_farma: Mapped[str | None] = mapped_column(String(30))  # FF del ICI (código crudo)
    tipo: Mapped[str | None] = mapped_column(String(5))  # MEDTIP: M=medicamento, I=insumo
    es_petitorio: Mapped[bool | None] = mapped_column(Boolean)  # derivado de MEDPET == "P"
    medpet: Mapped[str | None] = mapped_column(String(5))  # MEDPET crudo: P=petitorio, _=SIS
    medest: Mapped[str | None] = mapped_column(String(5))  # MEDEST crudo: E / S / _
    es_estrategico: Mapped[bool | None] = mapped_column(Boolean)
    controlado: Mapped[bool | None] = mapped_column(Boolean)
    stock_min: Mapped[int | None] = mapped_column(Integer)
    stock_max: Mapped[int | None] = mapped_column(Integer)
    punto_reposicion: Mapped[int | None] = mapped_column(Integer)
    reg_sanitario: Mapped[str | None] = mapped_column(String(30))
    # Origen del catálogo: "MPRODUCTO" (catálogo oficial del almacén) o "ICI"
    # (solo aparece en los ICI de establecimientos, no en el catálogo oficial).
    origen: Mapped[str | None] = mapped_column(String(10))
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
