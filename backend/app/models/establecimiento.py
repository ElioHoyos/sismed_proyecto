"""Catálogo de establecimientos — carga manual, el ETL nunca escribe aquí."""
from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Establecimiento(Base):
    __tablename__ = "establecimiento"

    id: Mapped[int] = mapped_column(primary_key=True)
    cod_2000: Mapped[str] = mapped_column(String(20), unique=True)
    nombre: Mapped[str] = mapped_column(String(255))
    clasificacion: Mapped[str | None] = mapped_column(String(100))
    tipo: Mapped[str | None] = mapped_column(String(100))
    categoria: Mapped[str | None] = mapped_column(String(20))
    cod_microrred: Mapped[str | None] = mapped_column(String(20))
    nom_microrred: Mapped[str | None] = mapped_column(String(255))
    cod_red: Mapped[str | None] = mapped_column(String(20))
    red: Mapped[str | None] = mapped_column(String(255))
    ubigeo: Mapped[str | None] = mapped_column(String(10))
    distrito: Mapped[str | None] = mapped_column(String(100))
    provincia: Mapped[str | None] = mapped_column(String(100))
    departamento: Mapped[str | None] = mapped_column(String(100))
    tiene_sismed: Mapped[bool] = mapped_column(Boolean, default=False)
    es_almacen: Mapped[bool] = mapped_column(Boolean, default=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True)
