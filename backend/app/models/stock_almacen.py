"""Stock unificado (tabla `stock`): una sola tabla para el stock del ALMACÉN
central (por lote, con vencimiento — fuente MSTKALMDE) y el de los
ESTABLECIMIENTOS (por producto, sin lote — fuente STOCK del ICI). El `origen`
distingue ambos; `lote`/`fecha_vcto` existen solo para el almacén y
`establecimiento_id` solo para EESS. Así la consulta de negativos es una sola
para ambos casos. Ver app/etl/stock_almacen.py y app/etl/ici.py."""
from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base

ORIGEN_ALMACEN = "ALMACEN"
ORIGEN_EESS = "EESS"  # stock del ICI: por producto, sin lote
# Stock por lote de un establecimiento con SISMED propio (archivo MSTKALMDE del
# puesto, misma estructura que el del almacén). Origen SEPARADO de EESS (el del
# ICI) para que reimportar el ICI no borre el stock por lote y viceversa; trae
# lote + vencimiento y alimenta Vencimientos y negativos por lote, nunca el CPMA.
ORIGEN_EESS_LOTE = "EESS_LOTE"


class StgStockAlmacen(Base):
    __tablename__ = "stg_stock_almacen"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    importacion_id: Mapped[int] = mapped_column(ForeignKey("importacion.id", ondelete="CASCADE"))

    almcod: Mapped[str | None] = mapped_column(String(20))
    medcod: Mapped[str | None] = mapped_column(String(20))
    medlote: Mapped[str | None] = mapped_column(String(80))
    medfechvto: Mapped[str | None] = mapped_column(String(20))
    stksaldode: Mapped[str | None] = mapped_column(String(20))
    stkprecio: Mapped[str | None] = mapped_column(String(20))
    medregsan: Mapped[str | None] = mapped_column(String(80))


class StockFueraCatalogo(Base):
    """Stock por lote de productos que NO están en el catálogo del almacén
    (MEDCOD sin registro en `producto`). No se importan a `stock` ni se crean en
    el catálogo — el puesto los maneja por vía externa (DIRESA/CENARES/donación,
    se ven por sufijos de lote -DIR/-CEN). Se guardan aparte solo como reporte a
    revisar, por establecimiento. Es una foto: cada importación reemplaza la de
    esa ubicación. Ver app/etl/stock_almacen.py."""
    __tablename__ = "stock_fuera_catalogo"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origen: Mapped[str] = mapped_column(String(10))  # ALMACEN | EESS_LOTE
    almacen_cod: Mapped[str | None] = mapped_column(String(20))  # ALMACEN
    establecimiento_id: Mapped[int | None] = mapped_column(ForeignKey("establecimiento.id"))  # EESS
    medcod: Mapped[str] = mapped_column(String(20))  # código NO presente en el catálogo
    lote: Mapped[str] = mapped_column(String(80))
    fecha_vcto: Mapped[date | None] = mapped_column(Date)
    cantidad: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    precio: Mapped[float | None] = mapped_column(Numeric(14, 4))
    reg_sanitario: Mapped[str | None] = mapped_column(String(80))
    periodo: Mapped[date | None] = mapped_column(Date)
    importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
    actualizado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Stock(Base):
    __tablename__ = "stock"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    origen: Mapped[str] = mapped_column(String(10))  # ALMACEN | EESS
    # Solo uno de estos dos identifica la ubicación según el origen:
    almacen_cod: Mapped[str | None] = mapped_column(String(20))  # ALMACEN
    establecimiento_id: Mapped[int | None] = mapped_column(ForeignKey("establecimiento.id"))  # EESS
    producto_id: Mapped[int] = mapped_column(ForeignKey("producto.id"))
    # lote/fecha_vcto existen solo para el almacén (el ICI es por producto, sin lote):
    lote: Mapped[str | None] = mapped_column(String(80))
    fecha_vcto: Mapped[date | None] = mapped_column(Date)
    cantidad: Mapped[float] = mapped_column(Numeric(14, 2), default=0)
    precio: Mapped[float | None] = mapped_column(Numeric(14, 4))
    reg_sanitario: Mapped[str | None] = mapped_column(String(80))
    periodo: Mapped[date | None] = mapped_column(Date)  # foto de stock (cierre EESS / foto almacén)
    importacion_id: Mapped[int | None] = mapped_column(ForeignKey("importacion.id"))
    actualizado: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
