import { useEffect, useMemo, useState, type CSSProperties } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { useNavegacion } from "../navegacion";
import { useVencimientos } from "../hooks/useVencimientos";
import { GrupoPills } from "../components/filtros/GrupoPills";
import { SelectorBuscable } from "../components/filtros/SelectorBuscable";
import { ChipsActivos, type ChipActivo } from "../components/filtros/ChipsActivos";
import { BotonExportar } from "../components/BotonExportar";
import { descargarExport, obtenerEstablecimientosConLote } from "../services/api";
import {
  OPCIONES_FINANCIAMIENTO,
  OPCIONES_MEDEST,
  OPCIONES_TIPO,
  SIGNIFICADO_MEDEST,
  SIGNIFICADO_MEDPET,
  SIGNIFICADO_MEDTIP,
} from "../services/clasificacion";
import type { EstablecimientoConLote, FuenteVencimiento, VencimientoRow } from "../services/types";

type FiltroEstado = "TODOS" | "VENCIDO" | "PROXIMO_A_VENCER";
type Banda = "VENCIDO" | "CRITICO" | "PROXIMO";
type SortKey = "producto_nombre" | "fecha_vcto" | "saldo";
type SortDir = "asc" | "desc";

const DIAS_CRITICO = 30;

const META_BANDA: Record<
  Banda,
  { label: string; desc: string; color: string; bgFila: string; bgHeader: string }
> = {
  VENCIDO: {
    label: "Vencidos",
    desc: "Ya se perdió",
    color: "#dc3545",
    bgFila: "rgba(220,53,69,0.06)",
    bgHeader: "rgba(220,53,69,0.16)",
  },
  CRITICO: {
    label: "Crítico",
    desc: "Vence en ≤ 30 días",
    color: "#fd7e14",
    bgFila: "rgba(253,126,20,0.06)",
    bgHeader: "rgba(253,126,20,0.16)",
  },
  PROXIMO: {
    label: "Próximo",
    desc: "31 a 90 días",
    color: "#d9a406",
    bgFila: "rgba(240,173,78,0.07)",
    bgHeader: "rgba(240,173,78,0.18)",
  },
};
const BANDAS_ORDEN: Banda[] = ["VENCIDO", "CRITICO", "PROXIMO"];

function numero(valor: number): string {
  return valor.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
function fechaCorta(iso: string): string {
  const [a, m, d] = iso.split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}
function bandaDe(f: VencimientoRow): Banda {
  if (f.estado === "VENCIDO") return "VENCIDO";
  return f.dias_restantes <= DIAS_CRITICO ? "CRITICO" : "PROXIMO";
}

const CELDA: CSSProperties = { paddingTop: 14, paddingBottom: 14, verticalAlign: "middle" };

export function VencimientosPage() {
  const [fuente, setFuente] = useState<FuenteVencimiento>("ALMACEN");
  const [establecimientoCod, setEstablecimientoCod] = useState<string>("");
  const [conLote, setConLote] = useState<EstablecimientoConLote[]>([]);
  const [tipo, setTipo] = useState<string>("");
  const [financiamiento, setFinanciamiento] = useState<string>("");
  const [medest, setMedest] = useState<string>("");
  const { filas, hoy, cargando, error } = useVencimientos({ fuente, establecimientoCod, tipo, financiamiento, medest });
  const [filtro, setFiltro] = useState<FiltroEstado>("TODOS");
  const [busqueda, setBusqueda] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("saldo");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const esAlmacen = fuente === "ALMACEN";
  // Cuando se ven varios puestos a la vez, se muestra el establecimiento por fila.
  const mostrarEst = fuente === "EESS" && establecimientoCod === "";

  useEffect(() => {
    let vigente = true;
    obtenerEstablecimientosConLote()
      .then((l) => vigente && setConLote(l))
      .catch(() => {});
    return () => {
      vigente = false;
    };
  }, []);

  const { filtrosIniciales } = useNavegacion();
  useEffect(() => {
    if (!filtrosIniciales) return;
    if (filtrosIniciales.estado) setFiltro(filtrosIniciales.estado as FiltroEstado);
    setTipo(filtrosIniciales.tipo ?? "");
    setFinanciamiento(filtrosIniciales.financiamiento ?? "");
    setMedest(filtrosIniciales.medest ?? "");
  }, [filtrosIniciales]);

  function ordenarPor(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "producto_nombre" ? "asc" : "desc");
    }
  }

  const q = busqueda.trim().toLowerCase();
  const filasFiltradas = useMemo<VencimientoRow[]>(() => {
    return filas
      .filter((f) => filtro === "TODOS" || f.estado === filtro)
      .filter(
        (f) =>
          !q ||
          f.producto_nombre.toLowerCase().includes(q) ||
          (f.codigo_siga ?? "").toLowerCase().includes(q) ||
          f.lote.toLowerCase().includes(q),
      );
  }, [filas, filtro, q]);

  // Agrupar por banda y ordenar dentro de cada una (la banda = urgencia por
  // tiempo es el agrupador; el orden es secundario dentro de la banda).
  const porBanda = useMemo(() => {
    const grupos: Record<Banda, VencimientoRow[]> = { VENCIDO: [], CRITICO: [], PROXIMO: [] };
    for (const f of filasFiltradas) grupos[bandaDe(f)].push(f);
    const cmp = (a: VencimientoRow, b: VencimientoRow) => {
      let r = 0;
      if (sortKey === "producto_nombre") r = a.producto_nombre.localeCompare(b.producto_nombre, "es");
      else if (sortKey === "fecha_vcto") r = a.fecha_vcto.localeCompare(b.fecha_vcto);
      else r = a.saldo - b.saldo;
      return sortDir === "asc" ? r : -r;
    };
    for (const b of BANDAS_ORDEN) grupos[b].sort(cmp);
    return grupos;
  }, [filasFiltradas, sortKey, sortDir]);

  // Barras de proporción relativas al mayor saldo visible.
  const maxSaldo = useMemo(
    () => Math.max(1, ...filasFiltradas.map((f) => f.saldo)),
    [filasFiltradas],
  );

  // Tarjetas: resumen del conjunto cargado (todas las bandas).
  const resumen = useMemo(() => {
    const r: Record<Banda, { lotes: number; unidades: number }> = {
      VENCIDO: { lotes: 0, unidades: 0 },
      CRITICO: { lotes: 0, unidades: 0 },
      PROXIMO: { lotes: 0, unidades: 0 },
    };
    for (const f of filas) {
      const b = bandaDe(f);
      r[b].lotes += 1;
      r[b].unidades += f.saldo;
    }
    return r;
  }, [filas]);

  const totalFiltradas = filasFiltradas.length;

  const chipsVenc: ChipActivo[] = [];
  if (filtro !== "TODOS")
    chipsVenc.push({ clave: "estado", etiqueta: `Estado: ${filtro === "VENCIDO" ? "Vencidos" : "Por vencer"}`, onQuitar: () => setFiltro("TODOS") });
  if (tipo) chipsVenc.push({ clave: "tipo", etiqueta: `Tipo: ${SIGNIFICADO_MEDTIP[tipo]} (${tipo})`, onQuitar: () => setTipo("") });
  if (financiamiento) chipsVenc.push({ clave: "fin", etiqueta: `Financiamiento: ${SIGNIFICADO_MEDPET[financiamiento]} (${financiamiento})`, onQuitar: () => setFinanciamiento("") });
  if (medest) chipsVenc.push({ clave: "medest", etiqueta: `MEDEST: ${SIGNIFICADO_MEDEST[medest]} (${medest})`, onQuitar: () => setMedest("") });
  if (busqueda.trim()) chipsVenc.push({ clave: "busq", etiqueta: `Buscar: "${busqueda.trim()}"`, onQuitar: () => setBusqueda("") });

  function limpiarVenc() {
    setFiltro("TODOS");
    setTipo("");
    setFinanciamiento("");
    setMedest("");
    setBusqueda("");
  }

  function exportar(formato: "xlsx" | "pdf") {
    return descargarExport("/api/stock/vencimientos/export", {
      formato,
      fuente,
      establecimiento_cod: fuente === "EESS" ? establecimientoCod || undefined : undefined,
      estado: filtro !== "TODOS" ? filtro : undefined,
      tipo: tipo || undefined,
      financiamiento: financiamiento || undefined,
      medest: medest || undefined,
      buscar: busqueda.trim() || undefined,
    });
  }

  const nombrePuesto = conLote.find((e) => e.cod_2000 === establecimientoCod)?.nombre;

  return (
    <AppLayout titulo={esAlmacen ? "Vencimientos del almacén" : "Vencimientos por establecimiento"}>
      <div className="alert alert-info d-flex align-items-start gap-2" role="note">
        <i className="bi bi-info-circle-fill mt-1" aria-hidden="true" />
        <span>
          Cubre el <strong>stock por lote</strong>: el <strong>almacén central</strong> y los{" "}
          <strong>establecimientos con SISMED propio</strong> que subieron su stock por lote (MSTKALMDE).
          Los puestos de <strong>solo ICI no tienen vencimientos</strong> (el ICI no trae lote ni
          fecha). Lotes con stock, ordenados por urgencia. Calculado contra hoy
          {hoy ? ` (${fechaCorta(hoy)})` : ""}.
        </span>
      </div>

      {/* Tarjetas resumen */}
      <div className="row g-3 mb-3">
        {BANDAS_ORDEN.map((b) => {
          const m = META_BANDA[b];
          const r = resumen[b];
          return (
            <div className="col-12 col-md-4" key={b}>
              <div className="card h-100" style={{ borderLeft: `4px solid ${m.color}` }}>
                <div className="card-body py-3">
                  <div className="text-body-secondary small text-uppercase fw-semibold" style={{ color: m.color }}>
                    {m.label}
                  </div>
                  <div className="d-flex align-items-baseline gap-2">
                    <span className="fs-3 fw-bold">{r.lotes}</span>
                    <span className="text-body-secondary">lote{r.lotes === 1 ? "" : "s"}</span>
                  </div>
                  <div className="text-body-secondary small">
                    <strong>{numero(r.unidades)}</strong> unidades{" "}
                    {b === "VENCIDO" ? "perdidas" : "en riesgo"}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Filtros */}
      <div className="card mb-2">
        <div className="card-body d-flex flex-wrap gap-4 align-items-end">
          <GrupoPills
            label="Fuente"
            incluirTodos={false}
            valor={fuente}
            onChange={(v) => setFuente(v as FuenteVencimiento)}
            opciones={[
              { value: "ALMACEN", label: "Almacén central" },
              { value: "EESS", label: "Establecimientos" },
            ]}
          />
          {!esAlmacen && (
            <div style={{ minWidth: 240 }}>
              <SelectorBuscable
                label="Establecimiento (con stock por lote)"
                opciones={conLote.map((e) => ({ value: e.cod_2000, label: e.nombre }))}
                valor={establecimientoCod}
                onChange={setEstablecimientoCod}
                placeholder={conLote.length ? "Buscar establecimiento…" : "Ninguno con stock por lote"}
                etiquetaTodos="— Todos los que aportaron lote —"
              />
            </div>
          )}
          <GrupoPills
            label="Estado"
            etiquetaTodos="Todos"
            valor={filtro}
            onChange={(v) => setFiltro(v as FiltroEstado)}
            opciones={[
              { value: "VENCIDO", label: `Vencidos (${resumen.VENCIDO.lotes})`, color: "#dc3545" },
              { value: "PROXIMO_A_VENCER", label: `Por vencer (${resumen.CRITICO.lotes + resumen.PROXIMO.lotes})`, color: "#fd7e14" },
            ]}
          />
          <GrupoPills label="Tipo (M/I)" valor={tipo} onChange={setTipo} opciones={OPCIONES_TIPO} />
          <GrupoPills label="Financiamiento (_/P)" valor={financiamiento} onChange={setFinanciamiento} opciones={OPCIONES_FINANCIAMIENTO} />
          <GrupoPills label="MEDEST (E/S/_)" valor={medest} onChange={setMedest} opciones={OPCIONES_MEDEST} />
          <div style={{ flex: "2 1 280px", minWidth: 240 }}>
            <label className="form-label mb-1 d-block" htmlFor="buscar-venc">Buscar</label>
            <div className="input-group input-group-sm">
              <span className="input-group-text"><i className="bi bi-search" aria-hidden="true" /></span>
              <input
                id="buscar-venc"
                type="search"
                className="form-control"
                placeholder="Medicamento, código SIGA o lote…"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="d-flex justify-content-between align-items-start gap-2 flex-wrap">
        <ChipsActivos
          chips={chipsVenc}
          onLimpiar={limpiarVenc}
          contador={`${totalFiltradas} lote${totalFiltradas === 1 ? "" : "s"}`}
          cargando={cargando}
        />
        <BotonExportar onExportar={exportar} />
      </div>

      {error ? (
        <div className="alert alert-danger" role="alert">No se pudo cargar los vencimientos: {error}</div>
      ) : (
        <div className="card">
          <div className="card-body p-0" style={{ maxHeight: "72vh", overflow: "auto" }}>
            <table className="table table-hover mb-0">
              <thead className="sticky-top">
                <tr className="table-dark">
                  <ThSort label="Medicamento" col="producto_nombre" sortKey={sortKey} sortDir={sortDir} onSort={ordenarPor} />
                  <th style={{ ...CELDA }}>Lote</th>
                  <ThSort label="Vencimiento" col="fecha_vcto" sortKey={sortKey} sortDir={sortDir} onSort={ordenarPor} />
                  <ThSort label="Unidades" col="saldo" sortKey={sortKey} sortDir={sortDir} onSort={ordenarPor} alinearDerecha />
                </tr>
              </thead>
              <tbody>
                {BANDAS_ORDEN.map((b) => {
                  const rows = porBanda[b];
                  if (rows.length === 0) return null;
                  const m = META_BANDA[b];
                  const unidades = rows.reduce((s, f) => s + f.saldo, 0);
                  return (
                    <BandaSeccion key={b} banda={b} meta={m} lotes={rows.length} unidades={unidades} filas={rows} maxSaldo={maxSaldo} mostrarEst={mostrarEst} />
                  );
                })}
              </tbody>
            </table>

            {cargando && <div className="text-center text-body-secondary p-4">Cargando…</div>}
            {!cargando && filas.length === 0 && (
              <div className="text-center text-body-secondary p-5">
                {!esAlmacen && conLote.length === 0 ? (
                  <>
                    <i className="bi bi-inbox fs-2 d-block mb-2" aria-hidden="true" />
                    Ningún establecimiento ha subido stock por lote todavía. Cárgalo en{" "}
                    <em>Carga de archivos</em> (archivo MSTKALMDE del puesto).
                  </>
                ) : (
                  <>
                    <i className="bi bi-check2-circle fs-2 d-block mb-2 text-success" aria-hidden="true" />
                    No hay lotes vencidos ni próximos a vencer en{" "}
                    {esAlmacen ? "el almacén" : nombrePuesto ?? "los establecimientos"}.
                  </>
                )}
              </div>
            )}
            {!cargando && filas.length > 0 && totalFiltradas === 0 && (
              <div className="text-center text-body-secondary p-4">Ningún lote coincide con el filtro.</div>
            )}
          </div>
        </div>
      )}
    </AppLayout>
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
    <th
      role="button"
      onClick={() => onSort(col)}
      className={`user-select-none ${alinearDerecha ? "text-end" : ""}`}
      style={{ ...CELDA, cursor: "pointer" }}
      aria-sort={activa ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
    >
      {label}{" "}
      <i
        className={`bi ${activa ? (sortDir === "asc" ? "bi-caret-up-fill" : "bi-caret-down-fill") : "bi-arrow-down-up"}`}
        style={{ opacity: activa ? 1 : 0.4, fontSize: "0.75em" }}
        aria-hidden="true"
      />
    </th>
  );
}

function BandaSeccion({
  banda,
  meta,
  lotes,
  unidades,
  filas,
  maxSaldo,
  mostrarEst,
}: {
  banda: Banda;
  meta: (typeof META_BANDA)[Banda];
  lotes: number;
  unidades: number;
  filas: VencimientoRow[];
  maxSaldo: number;
  mostrarEst: boolean;
}) {
  return (
    <>
      <tr>
        <td colSpan={4} style={{ backgroundColor: meta.bgHeader, padding: "8px 12px" }}>
          <span className="fw-bold" style={{ color: meta.color }}>
            <i className="bi bi-circle-fill me-2" style={{ fontSize: "0.6em", verticalAlign: "middle" }} aria-hidden="true" />
            {meta.label.toUpperCase()}
          </span>
          <span className="text-body-secondary ms-2">— {meta.desc}</span>
          <span className="float-end fw-semibold">
            {lotes} lote{lotes === 1 ? "" : "s"} · {numero(unidades)} unidades
          </span>
        </td>
      </tr>
      {filas.map((f, i) => (
        <tr key={`${f.producto_cod}-${f.lote}-${i}`} style={{ backgroundColor: meta.bgFila }}>
          <td style={{ ...CELDA, boxShadow: `inset 3px 0 0 ${meta.color}`, minWidth: "22rem" }}>
            <div className="fw-semibold" style={{ fontSize: "1rem", lineHeight: 1.25 }}>
              {f.producto_nombre}
            </div>
            <div className="text-body-secondary d-flex align-items-center gap-2 flex-wrap mt-1" style={{ fontSize: "0.75rem" }}>
              <span className="badge text-bg-light border" title={SIGNIFICADO_MEDTIP[f.medtip ?? ""] ?? "Tipo"}>
                {f.medtip ?? "—"}
              </span>
              <span className="badge text-bg-light border" title={SIGNIFICADO_MEDPET[f.medpet ?? ""] ?? "Financiamiento"}>
                {f.medpet ?? "—"}
              </span>
              <span className="badge text-bg-light border" title={SIGNIFICADO_MEDEST[f.medest ?? ""] ?? "MEDEST"}>
                {f.medest ?? "—"}
              </span>
              <span>SIGA {f.codigo_siga ?? "—"}</span>
              <span>· Cód {f.producto_cod}</span>
              {mostrarEst && f.establecimiento_nombre && (
                <span className="badge text-bg-primary-subtle border" title="Establecimiento">
                  <i className="bi bi-hospital me-1" aria-hidden="true" />
                  {f.establecimiento_nombre}
                </span>
              )}
            </div>
          </td>
          <td style={{ ...CELDA }}>
            <code>{f.lote}</code>
          </td>
          <td style={{ ...CELDA }}>
            <CeldaVencimiento f={f} banda={banda} color={meta.color} />
          </td>
          <td style={{ ...CELDA }}>
            <CeldaUnidades saldo={f.saldo} maxSaldo={maxSaldo} color={meta.color} />
          </td>
        </tr>
      ))}
    </>
  );
}

function CeldaVencimiento({ f, banda, color }: { f: VencimientoRow; banda: Banda; color: string }) {
  const fecha = fechaCorta(f.fecha_vcto);
  if (banda === "VENCIDO") {
    return (
      <>
        <div>{fecha}</div>
        <span className="badge text-bg-danger mt-1">
          <i className="bi bi-x-octagon-fill me-1" aria-hidden="true" />
          hace {Math.abs(f.dias_restantes)} días
        </span>
      </>
    );
  }
  // Proximidad: más lleno = más cerca de vencer (0..90 días).
  const fill = Math.max(0, Math.min(1, (90 - f.dias_restantes) / 90));
  return (
    <>
      <div>{fecha}</div>
      <div className="d-flex align-items-center gap-2 mt-1">
        <div style={{ width: 64, height: 6, background: "#e9ecef", borderRadius: 3, overflow: "hidden" }}>
          <div style={{ width: `${fill * 100}%`, height: "100%", background: color }} />
        </div>
        <span className="small text-nowrap">en {f.dias_restantes} d</span>
      </div>
    </>
  );
}

function CeldaUnidades({ saldo, maxSaldo, color }: { saldo: number; maxSaldo: number; color: string }) {
  const fill = Math.max(0.04, saldo / maxSaldo);
  return (
    <div className="text-end">
      <div className="fw-bold" style={{ fontSize: "1.15rem", lineHeight: 1.1 }}>
        {numero(saldo)}
      </div>
      <div style={{ height: 6, background: "#e9ecef", borderRadius: 3, overflow: "hidden", marginTop: 3 }}>
        <div style={{ width: `${fill * 100}%`, height: "100%", background: color, marginLeft: "auto" }} />
      </div>
    </div>
  );
}
