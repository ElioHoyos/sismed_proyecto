import type {
  AsistenteRespuesta,
  CampoEditableCompra,
  CompraResponse,
  ConsolidadoResponse,
  DisponibilidadListResponse,
  DisponibilidadRedListResponse,
  EstablecimientoConLote,
  EstablecimientoOut,
  EventoImportacion,
  FiltroHistorial,
  FueraCatalogoResponse,
  FuenteVencimiento,
  HistorialResponse,
  HistorialResumen,
  ClasificacionResponse,
  ConsumoResponse,
  Granularidad,
  KardexResponse,
  MovimEstablecimiento,
  IncidenciaOut,
  PreviewResponse,
  ResumenLoteImportacion,
  ResumenSituacionRedResponse,
  OrigenStock,
  StockListResponse,
  VencimientosResponse,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

async function apiGet<T>(path: string, params: Record<string, string | undefined> = {}): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== "") url.searchParams.set(clave, valor);
  }

  const respuesta = await fetch(url.toString());
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    throw new Error(`GET ${path} → ${respuesta.status}: ${cuerpo}`);
  }
  return (await respuesta.json()) as T;
}

async function apiPostForm<T>(path: string, form: FormData): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  const respuesta = await fetch(url.toString(), { method: "POST", body: form });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    // FastAPI devuelve {"detail": "..."} — mostrar solo eso, sin ruido HTTP.
    let mensaje = cuerpo;
    try {
      const json = JSON.parse(cuerpo);
      if (typeof json?.detail === "string") mensaje = json.detail;
    } catch {
      /* cuerpo no-JSON: se usa tal cual */
    }
    throw new Error(mensaje || `POST ${path} → ${respuesta.status}`);
  }
  return (await respuesta.json()) as T;
}

export function obtenerDisponibilidad(params: {
  periodo?: string;
}): Promise<DisponibilidadListResponse> {
  return apiGet<DisponibilidadListResponse>("/api/disponibilidad", params);
}

export function obtenerDisponibilidadRed(params: {
  periodo?: string;
}): Promise<DisponibilidadRedListResponse> {
  return apiGet<DisponibilidadRedListResponse>("/api/disponibilidad/red", params);
}

export function obtenerResumenSituacionRed(params: {
  periodo?: string;
}): Promise<ResumenSituacionRedResponse> {
  return apiGet<ResumenSituacionRedResponse>("/api/disponibilidad/red/resumen", params);
}

export function obtenerEstablecimientos(): Promise<EstablecimientoOut[]> {
  return apiGet<EstablecimientoOut[]>("/api/establecimientos");
}

/**
 * Paso 1: analiza los archivos sin escribir en la BD (tipo detectado + filas +
 * establecimiento para los ICI). `archivos` puede traer DBF sueltos y/o un .zip
 * (posiblemente mezclado); el backend lo expande y detecta el tipo de cada uno.
 */
export function previsualizar(archivos: File[]): Promise<PreviewResponse> {
  const form = new FormData();
  for (const archivo of archivos) form.append("archivos", archivo, archivo.name);
  return apiPostForm<PreviewResponse>("/api/importaciones/previsualizar", form);
}

/**
 * Paso 2: importa el lote. Se reenvían los mismos archivos crudos (DBF sueltos
 * y/o el .zip) y un mapa `asignaciones` nombre_dbf → cod_2000 (solo para los
 * ICI). El backend enruta cada archivo a su importador según el tipo detectado.
 */
export function importarLote(params: {
  archivos: File[];
  asignaciones: Record<string, string>;
  periodo: string;
  usuario?: string;
}): Promise<ResumenLoteImportacion> {
  const form = new FormData();
  for (const archivo of params.archivos) form.append("archivos", archivo, archivo.name);
  form.append("asignaciones", JSON.stringify(params.asignaciones));
  form.append("periodo", params.periodo);
  if (params.usuario) form.append("usuario", params.usuario);
  return apiPostForm<ResumenLoteImportacion>("/api/importaciones", form);
}

export function obtenerIncidencias(importacionId: number): Promise<IncidenciaOut[]> {
  return apiGet<IncidenciaOut[]>(`/api/importaciones/${importacionId}/incidencias`);
}

/**
 * Importa el lote con PROGRESO EN VIVO: el backend transmite NDJSON (un evento
 * JSON por línea) y `onEvento` se invoca a medida que cada archivo pasa por
 * en cola → procesando → listo/error, más el recálculo final. Resuelve cuando
 * el stream termina; lanza si la petición falla al abrirse.
 */
export async function importarLoteStream(
  params: { archivos: File[]; asignaciones: Record<string, string>; periodo: string; usuario?: string },
  onEvento: (ev: EventoImportacion) => void,
): Promise<void> {
  const form = new FormData();
  for (const archivo of params.archivos) form.append("archivos", archivo, archivo.name);
  form.append("asignaciones", JSON.stringify(params.asignaciones));
  form.append("periodo", params.periodo);
  if (params.usuario) form.append("usuario", params.usuario);

  const url = new URL("/api/importaciones/stream", API_BASE_URL);
  const respuesta = await fetch(url.toString(), { method: "POST", body: form });
  if (!respuesta.ok || !respuesta.body) {
    const cuerpo = await respuesta.text().catch(() => "");
    let mensaje = cuerpo;
    try {
      const json = JSON.parse(cuerpo);
      if (typeof json?.detail === "string") mensaje = json.detail;
    } catch {
      /* cuerpo no-JSON */
    }
    throw new Error(mensaje || `POST /api/importaciones/stream → ${respuesta.status}`);
  }

  const reader = respuesta.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  const procesarLineas = () => {
    let idx: number;
    while ((idx = buffer.indexOf("\n")) >= 0) {
      const linea = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (linea) onEvento(JSON.parse(linea) as EventoImportacion);
    }
  };

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    procesarLineas();
  }
  buffer += decoder.decode();
  procesarLineas();
  const resto = buffer.trim();
  if (resto) onEvento(JSON.parse(resto) as EventoImportacion);
}

export function obtenerStock(params: {
  origen: OrigenStock;
  establecimientoCod?: string;
  soloNegativos?: boolean;
  tipo?: string;
  financiamiento?: string;
  medest?: string;
}): Promise<StockListResponse> {
  return apiGet<StockListResponse>("/api/stock", {
    origen: params.origen,
    establecimiento_cod: params.establecimientoCod || undefined,
    solo_negativos: params.soloNegativos ? "true" : undefined,
    tipo: params.tipo || undefined,
    financiamiento: params.financiamiento || undefined,
    medest: params.medest || undefined,
  });
}

export function obtenerCompraCentralizada(anio?: number): Promise<CompraResponse> {
  return apiGet<CompraResponse>("/api/compra-centralizada", {
    anio: anio !== undefined ? String(anio) : undefined,
  });
}

/** Establecimientos que aportaron stock por lote (para elegir en Stock/Vencimientos). */
export function obtenerEstablecimientosConLote(): Promise<EstablecimientoConLote[]> {
  return apiGet<EstablecimientoConLote[]>("/api/stock/establecimientos-con-lote");
}

/** Productos fuera del catálogo del almacén (stock por lote no importado) del
 * almacén o de un establecimiento. Dato a revisar, no error. */
export function obtenerFueraCatalogo(params: {
  origen: OrigenStock;
  establecimientoCod?: string;
}): Promise<FueraCatalogoResponse> {
  return apiGet<FueraCatalogoResponse>("/api/stock/fuera-catalogo", {
    origen: params.origen,
    establecimiento_cod: params.establecimientoCod || undefined,
  });
}

// ── Historial de correcciones (negativos por lote) ────────────────────

export function obtenerHistorial(params: {
  estado?: FiltroHistorial;
  origen?: string;
  establecimientoCod?: string;
  mes?: string;
}): Promise<HistorialResponse> {
  return apiGet<HistorialResponse>("/api/stock/historial", {
    estado: params.estado,
    origen: params.origen || undefined,
    establecimiento_cod: params.establecimientoCod || undefined,
    mes: params.mes || undefined,
  });
}

export function obtenerHistorialResumen(mes: string): Promise<HistorialResumen> {
  return apiGet<HistorialResumen>("/api/stock/historial/resumen", { mes });
}

// ── Movimientos (kardex) ──────────────────────────────────────────────

export function obtenerMovimEstablecimientos(): Promise<MovimEstablecimiento[]> {
  return apiGet<MovimEstablecimiento[]>("/api/movimientos/establecimientos");
}

export function obtenerKardex(params: {
  producto: string;
  establecimientoCod?: string;
  desde?: string;
  hasta?: string;
}): Promise<KardexResponse> {
  return apiGet<KardexResponse>("/api/movimientos/kardex", {
    producto: params.producto,
    establecimiento_cod: params.establecimientoCod || undefined,
    desde: params.desde || undefined,
    hasta: params.hasta || undefined,
  });
}

export function obtenerConsumo(params: {
  producto: string;
  establecimientoCod?: string;
  granularidad: Granularidad;
  desde?: string;
  hasta?: string;
}): Promise<ConsumoResponse> {
  return apiGet<ConsumoResponse>("/api/movimientos/consumo", {
    producto: params.producto,
    establecimiento_cod: params.establecimientoCod || undefined,
    granularidad: params.granularidad,
    desde: params.desde || undefined,
    hasta: params.hasta || undefined,
  });
}

export function obtenerClasificacionSalidas(params: {
  producto: string;
  establecimientoCod?: string;
  desde?: string;
  hasta?: string;
}): Promise<ClasificacionResponse> {
  return apiGet<ClasificacionResponse>("/api/movimientos/clasificacion", {
    producto: params.producto,
    establecimiento_cod: params.establecimientoCod || undefined,
    desde: params.desde || undefined,
    hasta: params.hasta || undefined,
  });
}

/** El informático marca una incidencia como revisada/corregida (quién + nota). */
export function marcarRevision(id: number, body: { revisado_por?: string; nota?: string }): Promise<{ ok: boolean }> {
  return apiSend<{ ok: boolean }>("PUT", `/api/stock/historial/${id}/revision`, body);
}

export function quitarRevision(id: number): Promise<{ ok: boolean }> {
  return apiSend<{ ok: boolean }>("DELETE", `/api/stock/historial/${id}/revision`);
}

/** Vencimientos por lote (vencidos + próximos a vencer): del almacén (fuente
 * ALMACEN) o de los establecimientos con stock por lote (fuente EESS). Los
 * filtros de tipo/financiamiento se aplican en el backend. */
export function obtenerVencimientos(params: {
  fuente?: FuenteVencimiento;
  establecimientoCod?: string;
  tipo?: string;
  financiamiento?: string;
  medest?: string;
} = {}): Promise<VencimientosResponse> {
  return apiGet<VencimientosResponse>("/api/stock/vencimientos", {
    fuente: params.fuente || undefined,
    establecimiento_cod: params.establecimientoCod || undefined,
    tipo: params.tipo || undefined,
    financiamiento: params.financiamiento || undefined,
    medest: params.medest || undefined,
  });
}

async function apiPostJson<T>(path: string, body: unknown): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  const respuesta = await fetch(url.toString(), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    throw new Error(`POST ${path} → ${respuesta.status}: ${cuerpo}`);
  }
  return (await respuesta.json()) as T;
}

async function apiSend<T>(method: "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const url = new URL(path, API_BASE_URL);
  const respuesta = await fetch(url.toString(), {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    throw new Error(`${method} ${path} → ${respuesta.status}: ${cuerpo}`);
  }
  return (await respuesta.json()) as T;
}

// ── Consolidado de Red ────────────────────────────────────────────────

export function obtenerConsolidado(params: {
  periodo?: string;
  compraAnio?: number;
}): Promise<ConsolidadoResponse> {
  return apiGet<ConsolidadoResponse>("/api/consolidado-red", {
    periodo: params.periodo,
    compra_anio: params.compraAnio !== undefined ? String(params.compraAnio) : undefined,
  });
}

/** Guarda (o actualiza) la edición del doc sobre un campo del bloque de compra.
 * Se guarda aparte del archivo → sobrevive a la re-importación del CENARES. */
export function guardarEdicionCompra(payload: {
  anio: number;
  codigo_sismed: string;
  campo: CampoEditableCompra;
  valor: string | null;
}): Promise<{ ok: boolean }> {
  return apiSend<{ ok: boolean }>("PUT", "/api/compra-centralizada/edicion", payload);
}

/** Quita la edición del doc → vuelve a mostrarse el valor del archivo. */
export function revertirEdicionCompra(params: {
  anio: number;
  codigo_sismed: string;
  campo: CampoEditableCompra;
}): Promise<{ ok: boolean }> {
  const q = new URLSearchParams({
    anio: String(params.anio),
    codigo_sismed: params.codigo_sismed,
    campo: params.campo,
  });
  return apiSend<{ ok: boolean }>("DELETE", `/api/compra-centralizada/edicion?${q.toString()}`);
}

/** Asistente de consultas local (reglas en el backend). `sesionId` liga las
 * reformulaciones: si una pregunta no se entendió y luego el doc reformula, el
 * backend aprende ese par. */
export function preguntarAsistente(pregunta: string, sesionId?: string): Promise<AsistenteRespuesta> {
  return apiPostJson<AsistenteRespuesta>("/api/asistente", { pregunta, sesion_id: sesionId });
}

/**
 * Descarga un archivo de exportación (Excel/PDF) generado en el backend con los
 * filtros dados. Trae el blob (para poder mostrar "generando…") y dispara la
 * descarga con el nombre que envía el servidor.
 */
export async function descargarExport(
  path: string,
  params: Record<string, string | number | boolean | undefined>,
): Promise<void> {
  const url = new URL(path, API_BASE_URL);
  for (const [clave, valor] of Object.entries(params)) {
    if (valor !== undefined && valor !== "" && valor !== false) url.searchParams.set(clave, String(valor));
  }

  const respuesta = await fetch(url.toString());
  if (!respuesta.ok) {
    const cuerpo = await respuesta.text();
    throw new Error(`No se pudo generar el archivo (${respuesta.status}): ${cuerpo.slice(0, 200)}`);
  }

  const blob = await respuesta.blob();
  const cd = respuesta.headers.get("Content-Disposition") ?? "";
  const m = /filename="?([^"]+)"?/.exec(cd);
  const nombre = m?.[1] ?? "reporte";

  const objUrl = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = objUrl;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(objUrl);
}
