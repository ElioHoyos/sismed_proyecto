"""StgIci: espejo crudo del DBF. Ici: tabla limpia, una fila por
establecimiento/producto/mes. Ver app/etl/ici.py."""
from sqlalchemy import BigInteger, ForeignKey, Numeric, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StgIci(Base):
    __tablename__ = "stg_ici"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    importacion_id: Mapped[int] = mapped_column(ForeignKey("importacion.id", ondelete="CASCADE"))

    codigo_med: Mapped[str | None] = mapped_column(String(20))
    descrip: Mapped[str | None] = mapped_column(String(255))
    medtip: Mapped[str | None] = mapped_column(String(5))
    medpet: Mapped[str | None] = mapped_column(String(5))
    medest: Mapped[str | None] = mapped_column(String(5))
    ff: Mapped[str | None] = mapped_column(String(20))

    mes01: Mapped[str | None] = mapped_column(String(20))
    mes02: Mapped[str | None] = mapped_column(String(20))
    mes03: Mapped[str | None] = mapped_column(String(20))
    mes04: Mapped[str | None] = mapped_column(String(20))
    mes05: Mapped[str | None] = mapped_column(String(20))
    mes06: Mapped[str | None] = mapped_column(String(20))
    mes07: Mapped[str | None] = mapped_column(String(20))
    mes08: Mapped[str | None] = mapped_column(String(20))
    mes09: Mapped[str | None] = mapped_column(String(20))
    mes10: Mapped[str | None] = mapped_column(String(20))
    mes11: Mapped[str | None] = mapped_column(String(20))
    mes12: Mapped[str | None] = mapped_column(String(20))

    stock: Mapped[str | None] = mapped_column(String(20))
    precio: Mapped[str | None] = mapped_column(String(20))

    cpa: Mapped[str | None] = mapped_column(String(20))
    situacion: Mapped[str | None] = mapped_column(String(20))


class Ici(Base):
    __tablename__ = "ici"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    establecimiento_id: Mapped[int] = mapped_column(ForeignKey("establecimiento.id"))
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    anio: Mapped[int] = mapped_column(SmallInteger)
    mes: Mapped[int] = mapped_column(SmallInteger)

    consumo: Mapped[float] = mapped_column(Numeric(14, 2), default=0)

    # NULL salvo en el mes de cierre de la importación que lo trajo.
    stock_final: Mapped[float | None] = mapped_column(Numeric(14, 2))
    precio: Mapped[float] = mapped_column(Numeric(14, 4), default=0)

    # Referencia de SISMED, no se usa para calcular.
    cpa_sismed: Mapped[float | None] = mapped_column(Numeric(14, 2))
    situacion_sismed: Mapped[str | None] = mapped_column(String(20))

    importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
