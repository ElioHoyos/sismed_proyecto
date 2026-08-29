export type Situacion =
  | "SIN ROTACION"
  | "DESABASTECIDO"
  | "CRITICO"
  | "SUBSTOCK"
  | "NORMOSTOCK"
  | "SOBRESTOCK";

export interface MesConsumo {
  anio: number;
  mes: number;
  nombre: string;
  consumo: number;
}

/** Clasificación cruda del catálogo (códigos del ICI/MPRODUCTO, tal cual el doc). */
export interface ClasificacionProducto {
  codigo_siga: string | null; // CODIGO SIGA
  medtip: string | null; // M/I
  medpet: string | null; // P/_
  medest: string | null; // E/S/_
  ff: string | null; // forma farmacéutica
}

export interface DisponibilidadEstablecimiento extends ClasificacionProducto {
  establecimiento_cod: string;
  establecimiento_nombre: string;
  producto_cod: string;
  producto_nombre: string;
  sumames: number;
  contador: number;
  cpma: number;
  stock_red: number; // stock de la Red (establecimiento)
  stock_aem: number; // Almacén Especializado de Medicamentos (central)
  dispo: number; // stock_red / cpma
  dispo_total: number; // (stock_red + stock_aem) / cpma
  situacion: Situacion;
  situacion_total: Situacion;
  meses: MesConsumo[];
}

export interface DisponibilidadRed extends ClasificacionProducto {
  producto_cod: string;
  producto_nombre: string;
  sumames: number;
  contador: number;
  cpma: number;
  stock_red: number; // stock de la Red (establecimiento)
  stock_aem: number; // Almacén Especializado de Medicamentos (central)
  dispo: number; // stock_red / cpma
  dispo_total: number; // (stock_red + stock_aem) / cpma
  situacion: Situacion;
  situacion_total: Situacion;
  meses: MesConsumo[];
}

export interface DisponibilidadListResponse {
  periodo: string | null;
  total: number;
  nota: string;
  resultados: DisponibilidadEstablecimiento[];
}

export interface DisponibilidadRedListResponse {
  periodo: string | null;
  total: number;
  resultados: DisponibilidadRed[];
}

export interface SituacionResumenItem {
  situacion: Situacion;
  cantidad: number;
  porcentaje: number;
}

export interface ResumenSituacionRedResponse {
  periodo: string | null;
  // Dos indicadores independientes por MEDEST (Estratégicos excluidos):
  total_soporte: number;
  total_sis: number;
  soporte: SituacionResumenItem[];
  sis: SituacionResumenItem[];
}

export type Vista = "establecimiento" | "red";

// ── Establecimientos y carga de ICI ──────────────────────────────────

export interface EstablecimientoOut {
  cod_2000: string;
  nombre: string;
}

export type ConfianzaDeteccion = "alta" | "dudosa" | "no_encontrado";

/** Tipo de archivo detectado por columnas (ver backend deteccion_tipo.py). */
export type TipoArchivo =
  | "ICI"
  | "STOCK_ALMACEN"
  | "CATALOGO"
  | "CENARES"
  | "MOVIM_CAB"
  | "MOVIM_DET"
  | "DESCONOCIDO";

export interface CandidatoEstablecimiento {
  cod_2000: string;
  nombre: string;
  score: number;
}

export interface PreviewArchivo {
  archivo: string;
  tipo: TipoArchivo;
  filas: number;
  confianza: ConfianzaDeteccion | null; // solo ICI
  establecimiento: CandidatoEstablecimiento | null; // solo ICI
  candidatos: CandidatoEstablecimiento[]; // solo ICI
  // Solo STOCK_ALMACEN: si el archivo es del almacén o de un establecimiento (por el ALMCOD)
  stock_origen: "ALMACEN" | "EESS" | "MIXTO" | null;
  stock_establecimiento_cod: string | null;
  stock_establecimiento_nombre: string | null;
  error: string | null;
}

export interface PreviewResponse {
  archivos: PreviewArchivo[];
}

export interface ResumenArchivoImportacion {
  archivo: string;
  tipo: TipoArchivo;
  importacion_id: number | null;
  establecimiento: string | null;
  filas: number;
  incidencias: number;
  estado: string; // OK | ERROR | OMITIDO
  error: string | null;
  detalle: string | null;
}

/** Un módulo que este lote actualizó, con enlace directo para saltar a verlo. */
export interface ModuloActualizado {
  pagina: string; // disponibilidad | consolidado | stock | vencimientos
  titulo: string;
  detalle: string;
}

export interface ResumenLoteImportacion {
  archivos: ResumenArchivoImportacion[];
  productos_recalculados: number;
  productos_red_recalculados: number;
  modulos: ModuloActualizado[];
}

/** Eventos del import en vivo (NDJSON): uno por línea desde /importaciones/stream. */
export type EventoImportacion =
  | { evento: "plan"; archivos: { archivo: string; tipo: TipoArchivo }[] }
  | { evento: "archivo_inicio"; archivo: string; tipo: TipoArchivo }
  | { evento: "archivo_fin"; resultado: ResumenArchivoImportacion }
  | { evento: "recalculo_inicio" }
  | { evento: "fin"; resumen: ResumenLoteImportacion }
  | { evento: "error"; error: string };

export interface IncidenciaOut {
  id: number;
  tipo: string;
  detalle: string | null;
  fila_id: number | null;
}

// ── Stock unificado (almacén por lote + establecimiento por producto) ──

export type OrigenStock = "ALMACEN" | "EESS";

export interface StockRow {
  origen: OrigenStock;
  producto_cod: string;
  producto_nombre: string;
  codigo_siga: string | null;
  medtip: string | null; // M/I
  medpet: string | null; // P/_
  medest: string | null; // E/S/_
  establecimiento_cod: string | null; // solo EESS
  establecimiento_nombre: string | null; // solo EESS
  almacen_cod: string | null; // solo ALMACEN
  lote: string | null; // solo ALMACEN (el ICI no trae lote)
  fecha_vcto: string | null; // solo ALMACEN
  saldo: number;
  saldo_consolidado: number;
  incidencia_id: number | null; // incidencia de historial (solo negativos por lote)
  revisado: boolean; // check del informático (misma tabla que el Historial)
  revisado_en: string | null; // fecha/hora del check
  nota: string | null; // nota opcional del check
}

export interface StockListResponse {
  origen: OrigenStock;
  por_lote: boolean; // true = filas por lote (almacén, o EESS con MSTKALMDE cargado)
  total: number;
  resultados: StockRow[];
}

/** Establecimiento que aportó stock por lote (los únicos con negativos por lote y vencimientos). */
export interface EstablecimientoConLote {
  cod_2000: string;
  nombre: string;
}

/** Producto con stock por lote que NO está en el catálogo del almacén (dato a
 * revisar; el puesto lo maneja por vía externa DIRESA/CENARES/donación). */
export interface FueraCatalogoRow {
  medcod: string;
  lote: string;
  fecha_vcto: string | null;
  saldo: number;
  precio: number | null;
  reg_sanitario: string | null;
  establecimiento_cod: string | null;
  establecimiento_nombre: string | null;
}

export interface FueraCatalogoResponse {
  origen: string;
  total: number;
  resultados: FueraCatalogoRow[];
}

export type EstadoVencimiento = "VENCIDO" | "PROXIMO_A_VENCER";
/** Fuente de los vencimientos: almacén central o establecimientos con stock por lote. */
export type FuenteVencimiento = "ALMACEN" | "EESS";

export interface VencimientoRow {
  codigo_siga: string | null;
  producto_cod: string;
  producto_nombre: string;
  medtip: string | null; // M/I
  medpet: string | null; // P/_
  medest: string | null; // E/S/_
  lote: string;
  fecha_vcto: string;
  dias_restantes: number; // negativo si ya venció
  saldo: number; // unidades
  estado: EstadoVencimiento;
  origen: string; // ALMACEN | EESS_LOTE
  establecimiento_cod: string | null; // solo EESS_LOTE
  establecimiento_nombre: string | null; // solo EESS_LOTE
  almacen_cod: string | null; // solo ALMACEN
}

export interface VencimientosResponse {
  hoy: string;
  ventana_dias: number;
  fuente: FuenteVencimiento;
  total: number;
  resultados: VencimientoRow[];
}

// ── Historial de correcciones de stock (negativos por lote) ──────────

export type EstadoHistorial = "PENDIENTE" | "RESUELTO";
export type FiltroHistorial = "pendientes" | "resueltos" | "todos";

export interface HistorialIncidencia {
  id: number;
  tipo: string;
  origen: string;
  almacen_cod: string | null;
  establecimiento_cod: string | null;
  establecimiento_nombre: string | null;
  producto_cod: string;
  producto_nombre: string;
  codigo_siga: string | null;
  lote: string;
  estado: EstadoHistorial;
  detectado_en: string;
  detectado_inicial: boolean; // sembrado del stock preexistente (fecha aproximada)
  valor_detectado: number;
  valor_actual: number;
  resuelto_en: string | null;
  valor_resuelto: number | null;
  dias: number; // días abierto (hasta resolverse o hasta hoy)
  revisado: boolean;
  revisado_por: string | null;
  revisado_en: string | null;
  nota: string | null;
}

export interface HistorialResponse {
  estado: string;
  total: number;
  resultados: HistorialIncidencia[];
}

export interface HistorialResumen {
  mes: string;
  negativos: number;
  resueltos: number;
  pendientes: number;
  pendientes_totales: number;
}

// ── Movimientos (kardex) ──────────────────────────────────────────────

export interface MovimEstablecimiento {
  cod_2000: string;
  nombre: string;
}

export interface ProductoInfo {
  producto_cod: string;
  producto_nombre: string;
  codigo_siga: string | null;
}

export interface KardexRow {
  fecha: string | null;
  tipo: string; // E | S
  lote: string | null;
  fecha_vcto: string | null;
  cantidad: number;
  categoria: string | null;
  establecimiento_cod: string | null;
  establecimiento_nombre: string | null;
  saldo: number;
}

export interface KardexResponse {
  producto: ProductoInfo;
  total: number;
  resultados: KardexRow[];
}

export type Granularidad = "dia" | "semana" | "mes";

export interface ConsumoPunto {
  periodo: string;
  salidas: number;
  movimientos: number;
}

export interface ConsumoResponse {
  producto: ProductoInfo;
  granularidad: string;
  cpma_referencia: number | null; // CPMA calculado (red), para validación cruzada
  total_salidas: number;
  resultados: ConsumoPunto[];
}

export interface ClasificacionItem {
  categoria: string;
  salidas: number;
  movimientos: number;
}

export interface ClasificacionResponse {
  producto: ProductoInfo;
  total_salidas: number;
  resultados: ClasificacionItem[];
}

// ── Compra centralizada (CENARES) ────────────────────────────────────

export interface CompraRegistro {
  codigo_sismed: string;
  codigo_siga: string | null;
  tipo_producto: string | null;
  procedimiento: string | null;
  estado_situacion: string | null;
  observacion_estado: string | null;
  reg_siga_situacion: string | null;
  reg_siga_observacion: string | null;
  contratista: string | null;
  nro_contrato: string | null;
  fecha_convocatoria: string | null;
  fecha_buena_pro: string | null;
  fecha_entrega: string | null;
  fecha_entrega_texto: string | null;
  observacion: string | null;
}

export interface CompraResponse {
  anio: number | null;
  anios_disponibles: number[];
  total: number;
  registros: CompraRegistro[];
}

// ── Consolidado de Red (ICI + cálculos + CENARES, como el DISPO_RED del doc) ──

/** Campos del bloque de compra que el doc edita a mano en el Consolidado (todo
 * el bloque CENARES menos TIPO PRODUCTO). En orden de columna. Debe calzar con
 * CAMPOS_EDITABLES del backend. */
export const CAMPOS_EDITABLES_COMPRA = [
  "procedimiento",
  "estado_situacion",
  "observacion_estado",
  "reg_siga_situacion",
  "reg_siga_observacion",
  "contratista",
  "nro_contrato",
  "fecha_convocatoria",
  "fecha_buena_pro",
  "fecha_entrega_texto",
  "observacion",
] as const;
export type CampoEditableCompra = (typeof CAMPOS_EDITABLES_COMPRA)[number];

/** Bloque "ESTADO COMPRA {año}" cruzado por Código SISMED = producto.medcod.
 * Valores finales (edición del doc donde exista). */
export interface CompraBloque {
  // No editables (vienen del archivo CENARES)
  tipo_producto: string | null;
  procedimiento: string | null;
  estado_situacion: string | null;
  observacion_estado: string | null;
  fecha_convocatoria: string | null;
  fecha_buena_pro: string | null;
  // Editables por el doc (su edición gana sobre el archivo)
  reg_siga_situacion: string | null;
  reg_siga_observacion: string | null;
  contratista: string | null;
  nro_contrato: string | null;
  fecha_entrega_texto: string | null;
  observacion: string | null;
  /** Campos que el doc editó a mano (para resaltar la celda). */
  editados: CampoEditableCompra[];
  /** true si no hay registro en CENARES → "Sin compra centralizada". */
  sin_registro: boolean;
}

export interface ConsolidadoRow extends ClasificacionProducto {
  producto_cod: string;
  producto_nombre: string;
  sumames: number;
  contador: number;
  cpma: number;
  precio: number;
  stock_red: number;
  stock_aem: number;
  dispo: number;
  dispo_total: number;
  situacion: Situacion;
  situacion_total: Situacion;
  meses: MesConsumo[];
  compra: CompraBloque;
}

export interface ConsolidadoResponse {
  periodo: string | null;
  compra_anio: number | null;
  anios_compra: number[];
  total: number;
  resultados: ConsolidadoRow[];
}

// ── Asistente ────────────────────────────────────────────────────────

export interface AsistenteDatos {
  columnas: string[];
  filas: string[][];
  total: number;
}

export interface AsistenteEnlace {
  pagina: string; // Pagina
  filtros: import("../navegacion").FiltrosIniciales;
}

export interface AsistenteRespuesta {
  intencion_detectada: string;
  respuesta_texto: string;
  datos: AsistenteDatos;
  sugerencias: string[];
  enlace: AsistenteEnlace | null;
}
