import { useEffect, useMemo, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { useNavegacion } from "../navegacion";
import { useEstablecimientos } from "../hooks/useEstablecimientos";
import { useStock } from "../hooks/useStock";
import { GrupoPills } from "../components/filtros/GrupoPills";
import { SelectorBuscable } from "../components/filtros/SelectorBuscable";
import { ChipsActivos, type ChipActivo } from "../components/filtros/ChipsActivos";
import { BotonExportar } from "../components/BotonExportar";
import { PanelFueraCatalogo } from "../components/PanelFueraCatalogo";
import { ControlRevisionStock } from "../components/ControlRevisionStock";
import { descargarExport, obtenerEstablecimientosConLote } from "../services/api";
import {
  OPCIONES_FINANCIAMIENTO,
  OPCIONES_MEDEST,
  OPCIONES_TIPO,
  SIGNIFICADO_MEDEST,
  SIGNIFICADO_MEDPET,
  SIGNIFICADO_MEDTIP,
} from "../services/clasificacion";
import type { OrigenStock, StockRow } from "../services/types";

type SortKey = "producto_nombre" | "saldo" | "fecha_vcto";
type SortDir = "asc" | "desc";
type Urgencia = "vencido" | "proximo" | null;

/** Un producto y sus lotes (visibles) en una ubicación, para la vista agrupada. */
interface GrupoProducto {
  cod: string;
  nombre: string;
  codigo_siga: string | null;
  medtip: string | null;
  medpet: string | null;
  medest: string | null;
  total: number; // total del producto (todos los lotes, incl. agotados)
  lotes: StockRow[]; // visibles, ordenados por vencimiento asc
  nActivos: number; // lotes con saldo > 0
  urgencia: Urgencia; // el más urgente entre sus lotes activos
  hayOculto: boolean; // algún lote negativo escondido en un total positivo
}

function numero(valor: number): string {
  return valor.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
function fechaCorta(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}
function diasHasta(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  const f = new Date(y, m - 1, d);
  f.setHours(0, 0, 0, 0);
  const hoy = new Date();
  hoy.setHours(0, 0, 0, 0);
  return Math.round((f.getTime() - hoy.getTime()) / 86_400_000);
}
/** Coherente con Vencimientos: vencido (< hoy) o próximo (≤ 90 días). */
function urgenciaDe(iso: string | null): Urgencia {
  if (!iso) return null;
  const d = diasHasta(iso);
  if (d < 0) return "vencido";
  if (d <= 90) return "proximo";
  return null;
}

export function StockPage() {
  const [origen, setOrigen] = useState<OrigenStock>("ALMACEN");
  const [establecimientoCod, setEstablecimientoCod] = useState<string>("");
  const [soloNegativos, setSoloNegativos] = useState<boolean>(true);
  const [tipo, setTipo] = useState<string>("");
  const [financiamiento, setFinanciamiento] = useState<string>("");
  const [medest, setMedest] = useState<string>("");
  const [busqueda, setBusqueda] = useState<string>("");
  const [sortKey, setSortKey] = useState<SortKey>("saldo");
  const [sortDir, setSortDir] = useState<SortDir>("asc");
  const [mostrarAgotados, setMostrarAgotados] = useState<boolean>(false);
  const [colapsados, setColapsados] = useState<Set<string>>(new Set());

  function toggleGrupo(cod: string) {
    setColapsados((prev) => {
      const n = new Set(prev);
      if (n.has(cod)) n.delete(cod);
      else n.add(cod);
      return n;
    });
  }

  const { establecimientos } = useEstablecimientos();
  const { filas, cargando, error, porLote, recargar } = useStock({ origen, establecimientoCod, soloNegativos, tipo, financiamiento, medest });
  const esAlmacen = origen === "ALMACEN";

  // Establecimientos que aportaron stock por lote (para marcarlos y explicar el modo).
  const [codsConLote, setCodsConLote] = useState<Set<string>>(new Set());
  useEffect(() => {
    let vigente = true;
    obtenerEstablecimientosConLote()
      .then((l) => vigente && setCodsConLote(new Set(l.map((e) => e.cod_2000))))
      .catch(() => {});
    return () => {
      vigente = false;
    };
  }, []);
  const puestoConLote = !esAlmacen && establecimientoCod !== "" && codsConLote.has(establecimientoCod);

  const { filtrosIniciales } = useNavegacion();
  useEffect(() => {
    if (!filtrosIniciales) return;
    if (filtrosIniciales.origen) setOrigen(filtrosIniciales.origen as OrigenStock);
    if (filtrosIniciales.soloNegativos !== undefined) setSoloNegativos(filtrosIniciales.soloNegativos);
    if (filtrosIniciales.establecimientoCod !== undefined) setEstablecimientoCod(filtrosIniciales.establecimientoCod);
    setTipo(filtrosIniciales.tipo ?? "");
    setFinanciamiento(filtrosIniciales.financiamiento ?? "");
    setMedest(filtrosIniciales.medest ?? "");
    setBusqueda(filtrosIniciales.busqueda ?? "");
  }, [filtrosIniciales]);

  function ordenarPor(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "producto_nombre" ? "asc" : "asc");
    }
  }

  const q = busqueda.trim().toLowerCase();
  const filasFiltradas = useMemo<StockRow[]>(() => {
    const base = !q
      ? filas
      : filas.filter(
          (f) =>
            f.producto_nombre.toLowerCase().includes(q) ||
            f.producto_cod.toLowerCase().includes(q) ||
            (f.codigo_siga ?? "").toLowerCase().includes(q) ||
            (f.lote ?? "").toLowerCase().includes(q),
        );
    const arr = [...base];
    arr.sort((a, b) => {
      let r = 0;
      if (sortKey === "producto_nombre") r = a.producto_nombre.localeCompare(b.producto_nombre, "es");
      else if (sortKey === "fecha_vcto") r = (a.fecha_vcto ?? "").localeCompare(b.fecha_vcto ?? "");
      else r = a.saldo - b.saldo;
      return sortDir === "asc" ? r : -r;
    });
    return arr;
  }, [filas, q, sortKey, sortDir]);

  // Oculta los lotes agotados (saldo 0) salvo que el doc pida verlos. Los
  // negativos (< 0) NO son agotados: siempre se muestran.
  const filasVisibles = useMemo<StockRow[]>(
    () => (mostrarAgotados ? filasFiltradas : filasFiltradas.filter((f) => f.saldo !== 0)),
    [filasFiltradas, mostrarAgotados],
  );

  // Vista por lote: agrupa por producto. Dentro del grupo, lotes por vencimiento
  // ascendente (lo que vence primero, arriba). Los grupos se ordenan según el
  // encabezado activo (nombre / total / vencimiento más urgente).
  const grupos = useMemo<GrupoProducto[]>(() => {
    if (!porLote) return [];
    const mapa = new Map<string, StockRow[]>();
    for (const f of filasVisibles) {
      const lista = mapa.get(f.producto_cod);
      if (lista) lista.push(f);
      else mapa.set(f.producto_cod, [f]);
    }
    const arr: GrupoProducto[] = [];
    for (const [cod, lotes] of mapa) {
      lotes.sort((a, b) => (a.fecha_vcto ?? "9999").localeCompare(b.fecha_vcto ?? "9999"));
      const primero = lotes[0];
      let urgencia: Urgencia = null;
      for (const l of lotes) {
        if (l.saldo <= 0) continue;
        const u = urgenciaDe(l.fecha_vcto);
        if (u === "vencido") { urgencia = "vencido"; break; }
        if (u === "proximo") urgencia = urgencia ?? "proximo";
      }
      arr.push({
        cod,
        nombre: primero.producto_nombre,
        codigo_siga: primero.codigo_siga,
        medtip: primero.medtip,
        medpet: primero.medpet,
        medest: primero.medest,
        total: primero.saldo_consolidado,
        lotes,
        nActivos: lotes.filter((l) => l.saldo > 0).length,
        urgencia,
        hayOculto: primero.saldo_consolidado >= 0 && lotes.some((l) => l.saldo < 0),
      });
    }
    const minSaldo = (g: GrupoProducto) => Math.min(...g.lotes.map((l) => l.saldo));
    arr.sort((a, b) => {
      let r = 0;
      if (sortKey === "producto_nombre") r = a.nombre.localeCompare(b.nombre, "es");
      else if (sortKey === "fecha_vcto")
        r = (a.lotes[0]?.fecha_vcto ?? "9999").localeCompare(b.lotes[0]?.fecha_vcto ?? "9999");
      else r = minSaldo(a) - minSaldo(b);
      return sortDir === "asc" ? r : -r;
    });
    return arr;
  }, [filasVisibles, porLote, sortKey, sortDir]);

  // Tarjetas resumen (sobre el conjunto cargado, respetando filtros del backend).
  const resumen = useMemo(() => {
    const negativos = filas.filter((f) => f.saldo < 0);
    const afectados = new Set(negativos.map((f) => f.producto_cod));
    return { total: filas.length, negativos: negativos.length, afectados: afectados.size };
  }, [filas]);

  const chips: ChipActivo[] = [];
  if (!esAlmacen && establecimientoCod) {
    const est = establecimientos.find((e) => e.cod_2000 === establecimientoCod);
    chips.push({ clave: "est", etiqueta: `Puesto: ${est?.nombre ?? establecimientoCod}`, onQuitar: () => setEstablecimientoCod("") });
  }
  if (soloNegativos) chips.push({ clave: "neg", etiqueta: "Solo negativos", onQuitar: () => setSoloNegativos(false) });
  if (tipo) chips.push({ clave: "tipo", etiqueta: `Tipo: ${SIGNIFICADO_MEDTIP[tipo]} (${tipo})`, onQuitar: () => setTipo("") });
  if (financiamiento) chips.push({ clave: "fin", etiqueta: `Financiamiento: ${SIGNIFICADO_MEDPET[financiamiento]} (${financiamiento})`, onQuitar: () => setFinanciamiento("") });
  if (medest) chips.push({ clave: "medest", etiqueta: `MEDEST: ${SIGNIFICADO_MEDEST[medest]} (${medest})`, onQuitar: () => setMedest("") });
  if (busqueda.trim()) chips.push({ clave: "busq", etiqueta: `Buscar: "${busqueda.trim()}"`, onQuitar: () => setBusqueda("") });

  function limpiar() {
    setSoloNegativos(false);
    setTipo("");
    setFinanciamiento("");
    setMedest("");
    setBusqueda("");
    if (!esAlmacen) setEstablecimientoCod("");
  }

  function exportar(formato: "xlsx" | "pdf") {
    return descargarExport("/api/stock/export", {
      formato,
      origen,
      establecimiento_cod: !esAlmacen ? establecimientoCod : undefined,
      solo_negativos: soloNegativos,
      tipo: tipo || undefined,
      financiamiento: financiamiento || undefined,
      medest: medest || undefined,
      buscar: busqueda.trim() || undefined,
    });
  }

  return (
    <AppLayout titulo="Stock">
      <div className="alert alert-info d-flex align-items-start gap-2 py-2" role="note">
        <i className="bi bi-info-circle-fill mt-1" aria-hidden="true" />
        <span className="small">
          El stock del <strong>almacén</strong> tiene detalle por lote y vencimiento. Un{" "}
          <strong>establecimiento</strong> con SISMED propio que subió su stock por lote (MSTKALMDE)
          también se ve por lote; los que solo tienen ICI van por producto (el ICI no trae lote). En
          SISMED un lote negativo queda <strong>escondido</strong> cuando el total del producto es
          positivo — esta pantalla los <strong>saca a la luz</strong> (marcados “oculto en el total”).
          Vienen así desde SISMED; se detectan y muestran, <strong>no se corrigen</strong>.
        </span>
      </div>

      {/* Tarjetas resumen */}
      <div className="row g-3 mb-3">
        <TarjetaResumen titulo={porLote ? "Lotes cargados" : "Productos"} valor={resumen.total} icono="bi-box-seam" color="#0d6efd" />
        <TarjetaResumen titulo="Saldos negativos" valor={resumen.negativos} icono="bi-dash-circle" color="#dc3545" />
        <TarjetaResumen titulo="Productos afectados" valor={resumen.afectados} icono="bi-capsule" color="#fd7e14" />
      </div>

      {/* Filtros */}
      <div className="card mb-2">
        <div className="card-body d-flex flex-wrap gap-4 align-items-end">
          <GrupoPills
            label="Origen"
            incluirTodos={false}
            valor={origen}
            onChange={(v) => setOrigen(v as OrigenStock)}
            opciones={[
              { value: "ALMACEN", label: "Almacén central" },
              { value: "EESS", label: "Establecimiento" },
            ]}
          />
          {!esAlmacen && (
            <div style={{ minWidth: 240 }}>
              <SelectorBuscable
                label="Establecimiento"
                opciones={establecimientos.map((e) => ({ value: e.cod_2000, label: e.nombre }))}
                valor={establecimientoCod}
                onChange={setEstablecimientoCod}
                placeholder="Buscar establecimiento…"
                etiquetaTodos="— Todos los puestos —"
              />
              {establecimientoCod !== "" && (
                <div className="form-text mt-1">
                  {puestoConLote ? (
                    <span className="text-success">
                      <i className="bi bi-box-seam me-1" aria-hidden="true" />
                      Aportó stock por lote: se ven lotes, vencimiento y negativos ocultos.
                    </span>
                  ) : (
                    <span>
                      <i className="bi bi-info-circle me-1" aria-hidden="true" />
                      Solo ICI: stock por producto (sin lote).
                    </span>
                  )}
                </div>
              )}
            </div>
          )}
          <GrupoPills label="Tipo (M/I)" valor={tipo} onChange={setTipo} opciones={OPCIONES_TIPO} />
          <GrupoPills label="Financiamiento (_/P)" valor={financiamiento} onChange={setFinanciamiento} opciones={OPCIONES_FINANCIAMIENTO} />
          <GrupoPills label="MEDEST (E/S/_)" valor={medest} onChange={setMedest} opciones={OPCIONES_MEDEST} />
          <div style={{ flex: "1 1 220px", minWidth: 200 }}>
            <label className="form-label mb-1 d-block" htmlFor="stock-busqueda">Buscar</label>
            <div className="input-group input-group-sm">
              <span className="input-group-text"><i className="bi bi-search" aria-hidden="true" /></span>
              <input
                id="stock-busqueda"
                type="search"
                className="form-control"
                placeholder={porLote ? "Nombre, código, SIGA o lote…" : "Nombre, código o SIGA…"}
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
              />
            </div>
          </div>
          <div className="align-self-end pb-1">
            <div className="form-check form-switch">
              <input id="stock-negativos" className="form-check-input" type="checkbox" role="switch" checked={soloNegativos} onChange={(e) => setSoloNegativos(e.target.checked)} />
              <label className="form-check-label" htmlFor="stock-negativos">Solo negativos</label>
            </div>
            {!soloNegativos && (
              <div className="form-check form-switch" title="Los lotes en 0 son históricos que SISMED conserva">
                <input id="stock-agotados" className="form-check-input" type="checkbox" role="switch" checked={mostrarAgotados} onChange={(e) => setMostrarAgotados(e.target.checked)} />
                <label className="form-check-label" htmlFor="stock-agotados">Mostrar agotados</label>
              </div>
            )}
          </div>
        </div>
      </div>

      <div className="d-flex justify-content-between align-items-start gap-2 flex-wrap">
        <ChipsActivos
          chips={chips}
          onLimpiar={limpiar}
          contador={
            porLote
              ? `${grupos.length} producto(s) · ${filasVisibles.length} lote(s)`
              : `${filasVisibles.length} producto(s)`
          }
          cargando={cargando}
        />
        <BotonExportar onExportar={exportar} />
      </div>

      <PanelFueraCatalogo origen={origen} establecimientoCod={esAlmacen ? "" : establecimientoCod} aplica={porLote} />

      {error ? (
        <div className="alert alert-danger" role="alert">No se pudo cargar el stock: {error}</div>
      ) : (
        <div className="card">
          <div className="card-body p-0" style={{ maxHeight: "70vh", overflow: "auto" }}>
            <table className="table table-hover mb-0 align-middle">
              <thead className="sticky-top">
                <tr className="table-dark">
                  <ThSort label="Medicamento" col="producto_nombre" sortKey={sortKey} sortDir={sortDir} onSort={ordenarPor} />
                  {porLote ? (
                    <th>Lote / Vence</th>
                  ) : (
                    <th>Establecimiento</th>
                  )}
                  <ThSort label={porLote ? "Saldo del lote" : "Saldo"} col="saldo" sortKey={sortKey} sortDir={sortDir} onSort={ordenarPor} alinearDerecha />
                  {porLote && (
                    <th className="text-end" title="Suma de todos los lotes del producto en esta ubicación">
                      Total del producto
                    </th>
                  )}
                </tr>
              </thead>
              <tbody>
                {porLote
                  ? grupos.map((g) => (
                      <FilasGrupo key={g.cod} grupo={g} colapsado={colapsados.has(g.cod)} onToggle={() => toggleGrupo(g.cod)} onRevisado={recargar} />
                    ))
                  : filasVisibles.map((f, i) => {
                      const neg = f.saldo < 0;
                      return (
                        <tr key={`${f.producto_cod}-${f.establecimiento_cod}-${i}`} style={neg ? { backgroundColor: "rgba(220,53,69,0.08)" } : undefined}>
                          <td style={{ paddingTop: 12, paddingBottom: 12, boxShadow: neg ? "inset 4px 0 0 #dc3545" : undefined, minWidth: "20rem" }}>
                            <InfoProducto f={f} />
                          </td>
                          <td className="text-body-secondary">{f.establecimiento_nombre}</td>
                          <td className="text-end">
                            <span className={`fw-bold ${neg ? "text-danger" : ""}`} style={{ fontSize: neg ? "1.35rem" : "1rem", lineHeight: 1 }}>
                              {numero(f.saldo)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
              </tbody>
            </table>

            {cargando && (
              <div className="text-center text-body-secondary p-4">
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                Consultando stock…
              </div>
            )}
            {!cargando && (porLote ? grupos.length === 0 : filasVisibles.length === 0) && (
              <EstadoVacio esAlmacen={esAlmacen} soloNegativos={soloNegativos} establecimientoCod={establecimientoCod} hayBusqueda={q.length > 0} />
            )}
          </div>
        </div>
      )}
    </AppLayout>
  );
}

function TarjetaResumen({ titulo, valor, icono, color }: { titulo: string; valor: number; icono: string; color: string }) {
  return (
    <div className="col-12 col-md-4">
      <div className="card h-100" style={{ borderLeft: `4px solid ${color}` }}>
        <div className="card-body d-flex align-items-center gap-3 py-3">
          <i className={`bi ${icono} fs-2`} style={{ color }} aria-hidden="true" />
          <div>
            <div className="fs-3 fw-bold" style={{ lineHeight: 1 }}>{valor.toLocaleString("es-PE")}</div>
            <div className="text-body-secondary small">{titulo}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

/** Bloque de M/I · _/P · E/S/_ + SIGA + Código, bajo el nombre del producto. */
function InfoProducto({ f }: { f: StockRow }) {
  return (
    <>
      <div className="fw-semibold" style={{ fontSize: "1rem", lineHeight: 1.25 }}>{f.producto_nombre}</div>
      <div className="text-body-secondary d-flex align-items-center gap-2 flex-wrap mt-1" style={{ fontSize: "0.75rem" }}>
        <span className="badge text-bg-light border" title={SIGNIFICADO_MEDTIP[f.medtip ?? ""] ?? "Tipo"}>{f.medtip ?? "—"}</span>
        <span className="badge text-bg-light border" title={SIGNIFICADO_MEDPET[f.medpet ?? ""] ?? "Financiamiento"}>{f.medpet ?? "—"}</span>
        <span className="badge text-bg-light border" title={SIGNIFICADO_MEDEST[f.medest ?? ""] ?? "MEDEST"}>{f.medest ?? "—"}</span>
        <span>SIGA {f.codigo_siga ?? "—"}</span>
        <span>· Cód {f.producto_cod}</span>
      </div>
    </>
  );
}

/** Punto de color en el encabezado del grupo: rojo (vencido) / naranja (próximo). */
function PuntoUrgencia({ u }: { u: Urgencia }) {
  if (!u) return null;
  const color = u === "vencido" ? "#dc3545" : "#fd7e14";
  const titulo = u === "vencido" ? "Tiene lotes vencidos" : "Tiene lotes próximos a vencer (≤ 90 días)";
  return (
    <span
      title={titulo}
      aria-label={titulo}
      style={{ display: "inline-block", width: 11, height: 11, borderRadius: "50%", background: color, flex: "0 0 auto", marginTop: 5 }}
    />
  );
}

function CeldaLoteVence({ f }: { f: StockRow }) {
  const u = urgenciaDe(f.fecha_vcto);
  return (
    <>
      <div><code>{f.lote ?? "—"}</code></div>
      <div className="small text-body-secondary">
        {f.fecha_vcto ? (
          <>
            vence {fechaCorta(f.fecha_vcto)}
            {u === "vencido" && <span className="badge text-bg-danger ms-2">vencido</span>}
            {u === "proximo" && <span className="badge text-bg-warning ms-2">por vencer</span>}
          </>
        ) : (
          "sin vcto"
        )}
      </div>
    </>
  );
}

function CeldaSaldo({ saldo }: { saldo: number }) {
  const neg = saldo < 0;
  return (
    <span className={`fw-bold ${neg ? "text-danger" : ""}`} style={{ fontSize: neg ? "1.35rem" : "1rem", lineHeight: 1 }}>
      {numero(saldo)}
    </span>
  );
}

/** Vista agrupada por producto (stock por lote). Un producto con varios lotes
 * activos se muestra como encabezado (nombre una vez, resumen y punto de
 * urgencia) + lotes indentados; con un solo lote, en una fila simple. */
function FilasGrupo({ grupo, colapsado, onToggle, onRevisado }: { grupo: GrupoProducto; colapsado: boolean; onToggle: () => void; onRevisado: () => void }) {
  // Un solo lote visible → fila simple, sin encabezado aparte.
  if (grupo.lotes.length === 1) {
    const f = grupo.lotes[0];
    const neg = f.saldo < 0;
    return (
      <tr style={neg ? { backgroundColor: "rgba(220,53,69,0.08)" } : undefined}>
        <td style={{ paddingTop: 12, paddingBottom: 12, boxShadow: neg ? "inset 4px 0 0 #dc3545" : undefined, minWidth: "20rem" }}>
          <div className="d-flex align-items-start gap-2">
            <PuntoUrgencia u={grupo.urgencia} />
            <div className="flex-grow-1"><InfoProducto f={f} /></div>
          </div>
        </td>
        <td>
          <CeldaLoteVence f={f} />
          {neg && <ControlRevisionStock incidenciaId={f.incidencia_id} revisado={f.revisado} revisadoEn={f.revisado_en} nota={f.nota} onCambio={onRevisado} />}
        </td>
        <td className="text-end"><CeldaSaldo saldo={f.saldo} /></td>
        <CeldaConsolidado saldo={f.saldo} consolidado={grupo.total} />
      </tr>
    );
  }

  const totalNeg = grupo.total < 0;
  return (
    <>
      {/* Encabezado del grupo: nombre + resumen (nº de lotes, total, urgencia). */}
      <tr className="table-light" style={{ borderTop: "2px solid #dee2e6" }}>
        <td style={{ paddingTop: 10, paddingBottom: 10, minWidth: "20rem" }}>
          <div className="d-flex align-items-start gap-2">
            <button
              type="button"
              className="btn btn-sm btn-link p-0 text-body-secondary lh-1"
              onClick={onToggle}
              aria-expanded={!colapsado}
              title={colapsado ? "Expandir" : "Plegar"}
            >
              <i className={`bi ${colapsado ? "bi-chevron-right" : "bi-chevron-down"}`} aria-hidden="true" />
            </button>
            <PuntoUrgencia u={grupo.urgencia} />
            <div className="flex-grow-1"><InfoProducto f={grupo.lotes[0]} /></div>
          </div>
        </td>
        <td className="small text-body-secondary align-middle">
          {grupo.nActivos} lote{grupo.nActivos === 1 ? "" : "s"} activo{grupo.nActivos === 1 ? "" : "s"}
          {grupo.lotes.length > grupo.nActivos && (
            <span className="text-body-tertiary"> · {grupo.lotes.length - grupo.nActivos} agotado(s)</span>
          )}
        </td>
        <td className="align-middle" />
        <td className="text-end align-middle">
          <div className="d-flex flex-column align-items-end">
            <span className={`fw-bold ${totalNeg ? "text-danger" : "text-success"}`} style={{ fontSize: "1.1rem", lineHeight: 1 }}>
              {numero(grupo.total)}
            </span>
            <span className="text-body-tertiary" style={{ fontSize: "0.7rem" }}>total del producto</span>
            {grupo.hayOculto && (
              <span className="badge text-bg-warning-subtle border mt-1" title="Uno de sus lotes es negativo y queda escondido en este total positivo">
                <i className="bi bi-eye-slash-fill me-1" aria-hidden="true" />
                negativo oculto
              </span>
            )}
          </div>
        </td>
      </tr>

      {/* Lotes indentados, por vencimiento asc; el nombre no se repite. */}
      {!colapsado &&
        grupo.lotes.map((f, i) => {
          const neg = f.saldo < 0;
          return (
            <tr key={`${f.lote}-${f.fecha_vcto ?? ""}-${i}`} style={neg ? { backgroundColor: "rgba(220,53,69,0.08)" } : undefined}>
              <td style={{ paddingLeft: "2.75rem", boxShadow: neg ? "inset 4px 0 0 #dc3545" : "inset 2px 0 0 #e9ecef" }}>
                <span className="text-body-tertiary small">
                  <i className="bi bi-arrow-return-right me-1" aria-hidden="true" />
                  lote
                </span>
              </td>
              <td>
                <CeldaLoteVence f={f} />
                {neg && <ControlRevisionStock incidenciaId={f.incidencia_id} revisado={f.revisado} revisadoEn={f.revisado_en} nota={f.nota} onCambio={onRevisado} />}
              </td>
              <td className="text-end"><CeldaSaldo saldo={f.saldo} /></td>
              {/* Total solo en el encabezado; en el lote, solo el callout de negativo oculto. */}
              <CeldaConsolidado saldo={f.saldo} consolidado={grupo.total} soloOculto />
            </tr>
          );
        })}
    </>
  );
}

/** Protagonista de la pantalla: cuando el lote es negativo pero el total del
 * producto es positivo, el negativo queda ESCONDIDO en el consolidado de SISMED.
 * Se muestra como una historia: −X escondido dentro de +Total. `soloOculto`
 * (filas de lote dentro de un grupo) muestra el callout solo si hay negativo
 * oculto; si no, celda vacía (el total va en el encabezado, no se repite). */
function CeldaConsolidado({ saldo, consolidado, soloOculto = false }: { saldo: number; consolidado: number; soloOculto?: boolean }) {
  const oculto = saldo < 0 && consolidado >= 0;

  if (oculto) {
    return (
      <td className="text-end">
        <div
          className="d-inline-flex flex-column align-items-end gap-1 p-2 rounded"
          style={{ background: "rgba(255,193,7,0.18)", border: "1px solid rgba(255,193,7,0.55)" }}
          title="El total del producto es positivo: por eso este negativo no se ve en el consolidado de SISMED"
        >
          <span className="fw-semibold d-flex align-items-center gap-1" style={{ color: "#9a6b00" }}>
            <i className="bi bi-eye-slash-fill" aria-hidden="true" />
            Oculto en el total
          </span>
          <span className="small text-nowrap">
            <span className="fw-bold text-danger">{numero(saldo)}</span>
            <i className="bi bi-arrow-right mx-1 text-body-secondary" aria-hidden="true" />
            escondido en <span className="fw-bold text-success">{numero(consolidado)}</span>
          </span>
        </div>
      </td>
    );
  }

  if (soloOculto) return <td />;

  return (
    <td className="text-end">
      <span className={consolidado >= 0 ? "text-success" : "text-danger"}>{numero(consolidado)}</span>
    </td>
  );
}

function ThSort({
  label,
  col,
  sortKey,
  sortDir,
  onSort,
  alinearDerecha,
}: {
  label: string;
  col: SortKey;
  sortKey: SortKey;
  sortDir: SortDir;
  onSort: (k: SortKey) => void;
  alinearDerecha?: boolean;
}) {
  const activa = sortKey === col;
  return (
    <th role="button" onClick={() => onSort(col)} className={`user-select-none ${alinearDerecha ? "text-end" : ""}`} style={{ cursor: "pointer" }} aria-sort={activa ? (sortDir === "asc" ? "ascending" : "descending") : "none"}>
      {label}{" "}
      <i className={`bi ${activa ? (sortDir === "asc" ? "bi-caret-up-fill" : "bi-caret-down-fill") : "bi-arrow-down-up"}`} style={{ opacity: activa ? 1 : 0.4, fontSize: "0.75em" }} aria-hidden="true" />
    </th>
  );
}

function EstadoVacio({
  esAlmacen,
  soloNegativos,
  establecimientoCod,
  hayBusqueda,
}: {
  esAlmacen: boolean;
  soloNegativos: boolean;
  establecimientoCod: string;
  hayBusqueda: boolean;
}) {
  let mensaje: string;
  let icono = "bi-inbox";
  let color = "text-body-secondary";
  if (hayBusqueda) {
    mensaje = "Ningún resultado coincide con la búsqueda. Prueba con otro término.";
  } else if (soloNegativos) {
    icono = "bi-check2-circle";
    color = "text-success";
    mensaje = esAlmacen
      ? "No hay saldos negativos en el almacén. 🎉"
      : establecimientoCod
        ? "No hay saldos negativos en este establecimiento."
        : "No hay saldos negativos en ningún establecimiento.";
  } else {
    mensaje = esAlmacen
      ? "No hay stock para mostrar."
      : "Selecciona un establecimiento o quita filtros para ver su stock.";
  }
  return (
    <div className={`text-center p-5 ${color}`}>
      <i className={`bi ${icono} fs-2 d-block mb-2`} aria-hidden="true" />
      {mensaje}
    </div>
  );
}
