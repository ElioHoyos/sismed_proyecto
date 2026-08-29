import { useEffect, useMemo, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { SelectorBuscable } from "../components/filtros/SelectorBuscable";
import { GrupoPills } from "../components/filtros/GrupoPills";
import {
  obtenerClasificacionSalidas,
  obtenerConsumo,
  obtenerKardex,
  obtenerMovimEstablecimientos,
} from "../services/api";
import type {
  ClasificacionResponse,
  ConsumoResponse,
  Granularidad,
  KardexResponse,
  MovimEstablecimiento,
} from "../services/types";

type Tab = "kardex" | "consumo" | "clasificacion";
type Consulta = { producto: string; establecimientoCod: string; desde: string; hasta: string };

const CAT_COLOR: Record<string, string> = {
  SIS: "#0d6efd",
  GENERAL: "#6c757d",
  "INTERV. SANITARIA": "#fd7e14",
  NOMINAL: "#198754",
};

function numero(v: number): string {
  return v.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
function fechaDia(iso: string | null): string {
  if (!iso) return "—";
  const [a, m, d] = iso.slice(0, 10).split("-");
  return d && m && a ? `${d}/${m}/${a}` : iso;
}
function mesLargo(periodo: string): string {
  const m = /^(\d{4})-(\d{2})$/.exec(periodo);
  if (!m) return periodo;
  const nombres = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Set", "Oct", "Nov", "Dic"];
  return `${nombres[+m[2] - 1]} ${m[1]}`;
}

// ── Tarjeta resumen (mismo lenguaje visual que Stock/Vencimientos) ──────────
function Tarjeta({ titulo, valor, icono, color, sub }: { titulo: string; valor: string; icono: string; color: string; sub?: string }) {
  return (
    <div className="col-6 col-lg-3">
      <div className="card h-100" style={{ borderLeft: `4px solid ${color}` }}>
        <div className="card-body d-flex align-items-center gap-3 py-3">
          <i className={`bi ${icono} fs-2`} style={{ color }} aria-hidden="true" />
          <div>
            <div className="fs-4 fw-bold" style={{ lineHeight: 1 }}>{valor}</div>
            <div className="text-body-secondary small">{titulo}</div>
            {sub && <div className="text-body-tertiary" style={{ fontSize: "0.72rem" }}>{sub}</div>}
          </div>
        </div>
      </div>
    </div>
  );
}

export function MovimientosPage() {
  const [productoInput, setProductoInput] = useState("");
  const [establecimientoCod, setEstablecimientoCod] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");
  const [consulta, setConsulta] = useState<Consulta | null>(null);
  const [tab, setTab] = useState<Tab>("kardex");
  const [granularidad, setGranularidad] = useState<Granularidad>("mes");

  const [establecimientos, setEstablecimientos] = useState<MovimEstablecimiento[]>([]);
  const [kardex, setKardex] = useState<KardexResponse | null>(null);
  const [consumo, setConsumo] = useState<ConsumoResponse | null>(null);
  const [clasif, setClasif] = useState<ClasificacionResponse | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    obtenerMovimEstablecimientos()
      .then((l) => {
        setEstablecimientos(l);
        if (l.length === 1) setEstablecimientoCod(l[0].cod_2000);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!consulta) return;
    let vig = true;
    setCargando(true);
    setError(null);
    const base = { producto: consulta.producto, establecimientoCod: consulta.establecimientoCod, desde: consulta.desde, hasta: consulta.hasta };
    const run =
      tab === "kardex"
        ? obtenerKardex(base).then((d) => vig && setKardex(d))
        : tab === "consumo"
          ? obtenerConsumo({ ...base, granularidad }).then((d) => vig && setConsumo(d))
          : obtenerClasificacionSalidas(base).then((d) => vig && setClasif(d));
    run
      .catch((e: unknown) => vig && setError(e instanceof Error ? e.message : "Error"))
      .finally(() => vig && setCargando(false));
    return () => {
      vig = false;
    };
  }, [consulta, tab, granularidad]);

  function buscar(e: React.FormEvent) {
    e.preventDefault();
    if (!productoInput.trim()) return;
    setConsulta({ producto: productoInput.trim(), establecimientoCod, desde, hasta });
  }

  const producto = kardex?.producto ?? consumo?.producto ?? clasif?.producto ?? null;

  return (
    <AppLayout titulo="Movimientos (kardex)">
      <div className="alert alert-info d-flex align-items-start gap-2 py-2" role="note">
        <i className="bi bi-shield-lock-fill mt-1" aria-hidden="true" />
        <span className="small">
          Entradas y salidas de un producto en el puesto. <strong>Sin datos de paciente</strong>: las salidas
          nominales se agrupan como “NOMINAL”, sin nombre, DNI ni diagnóstico.
        </span>
      </div>

      {/* Buscador */}
      <div className="card mb-3">
        <div className="card-body">
          <form className="d-flex flex-wrap gap-3 align-items-end" onSubmit={buscar}>
            <div style={{ flex: "1 1 260px", minWidth: 220 }}>
              <label className="form-label small mb-1 fw-semibold" htmlFor="mov-prod">Producto (nombre, código o SIGA)</label>
              <input id="mov-prod" className="form-control form-control-sm" placeholder="Ej. metamizol, 11372…" value={productoInput} onChange={(e) => setProductoInput(e.target.value)} />
            </div>
            <div style={{ minWidth: 220 }}>
              <SelectorBuscable
                label="Establecimiento"
                opciones={establecimientos.map((e) => ({ value: e.cod_2000, label: e.nombre }))}
                valor={establecimientoCod}
                onChange={setEstablecimientoCod}
                placeholder="Buscar…"
                etiquetaTodos="— Todos —"
              />
            </div>
            <div>
              <label className="form-label small mb-1 fw-semibold d-block">Desde</label>
              <input type="date" className="form-control form-control-sm" value={desde} onChange={(e) => setDesde(e.target.value)} />
            </div>
            <div>
              <label className="form-label small mb-1 fw-semibold d-block">Hasta</label>
              <input type="date" className="form-control form-control-sm" value={hasta} onChange={(e) => setHasta(e.target.value)} />
            </div>
            <button type="submit" className="btn btn-primary btn-sm" disabled={!productoInput.trim()}>
              <i className="bi bi-search me-1" aria-hidden="true" />
              Buscar
            </button>
          </form>
        </div>
      </div>

      {!consulta ? (
        <div className="card"><div className="card-body text-center text-body-secondary p-5">
          <i className="bi bi-arrow-left-right fs-2 d-block mb-2" aria-hidden="true" />
          Busca un producto para ver su kardex, consumo y clasificación de salidas.
        </div></div>
      ) : (
        <>
          {producto && (
            <div className="mb-3">
              <span className="fw-semibold fs-5">{producto.producto_nombre}</span>
              <span className="text-body-secondary small ms-2">Cód {producto.producto_cod} · SIGA {producto.codigo_siga ?? "—"}</span>
            </div>
          )}

          <ul className="nav nav-tabs mb-3">
            {([["kardex", "bi-journal-text", "Kardex"], ["consumo", "bi-graph-up", "Consumo"], ["clasificacion", "bi-pie-chart", "Clasificación"]] as [Tab, string, string][]).map(([t, ic, label]) => (
              <li className="nav-item" key={t}>
                <button type="button" className={`nav-link d-flex align-items-center gap-1 ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>
                  <i className={`bi ${ic}`} aria-hidden="true" />{label}
                </button>
              </li>
            ))}
          </ul>

          {error ? (
            <div className="alert alert-danger" role="alert">{error}</div>
          ) : cargando ? (
            <div className="text-center text-body-secondary p-5"><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />Cargando…</div>
          ) : tab === "kardex" ? (
            <VistaKardex data={kardex} />
          ) : tab === "consumo" ? (
            <VistaConsumo data={consumo} granularidad={granularidad} onGranularidad={setGranularidad} />
          ) : (
            <VistaClasificacion data={clasif} />
          )}
        </>
      )}
    </AppLayout>
  );
}

// ── Vista 1: Kardex (libreta de almacén) ────────────────────────────────────
function VistaKardex({ data }: { data: KardexResponse | null }) {
  const resumen = useMemo(() => {
    const rows = data?.resultados ?? [];
    const totalE = rows.filter((r) => r.tipo === "E").reduce((s, r) => s + r.cantidad, 0);
    const totalS = rows.filter((r) => r.tipo === "S").reduce((s, r) => s + r.cantidad, 0);
    const stock = rows.length ? rows[rows.length - 1].saldo : 0;
    // vencimientos del producto: lotes distintos con su vencimiento
    const vistos = new Map<string, string | null>();
    for (const r of rows) if (r.lote && !vistos.has(r.lote)) vistos.set(r.lote, r.fecha_vcto);
    const lotes = [...vistos.entries()].filter(([, v]) => v).sort((a, b) => (a[1] ?? "").localeCompare(b[1] ?? ""));
    return { totalE, totalS, stock, lotes };
  }, [data]);

  if (!data) return null;
  if (data.total === 0) return <div className="alert alert-secondary">Sin movimientos para este producto y filtros.</div>;

  let diaPrevio = "";
  return (
    <>
      <div className="row g-3 mb-3">
        <Tarjeta titulo="Stock actual" valor={numero(resumen.stock)} icono="bi-box-seam" color="#0d6efd" sub="saldo tras el último movimiento" />
        <Tarjeta titulo="Entró (período)" valor={`+${numero(resumen.totalE)}`} icono="bi-box-arrow-in-down" color="#198754" />
        <Tarjeta titulo="Salió (período)" valor={`−${numero(resumen.totalS)}`} icono="bi-box-arrow-up" color="#dc3545" />
        <Tarjeta titulo="Movimientos" valor={numero(data.total)} icono="bi-arrow-left-right" color="#6c757d" />
      </div>

      {resumen.lotes.length > 0 && (
        <div className="card mb-3">
          <div className="card-body py-2 d-flex flex-wrap align-items-center gap-2">
            <span className="small text-body-secondary me-1"><i className="bi bi-calendar-x me-1" aria-hidden="true" />Vencimientos:</span>
            {resumen.lotes.map(([lote, vto]) => (
              <span key={lote} className="badge text-bg-light border">
                <code className="me-1">{lote}</code> vence {fechaDia(vto)}
              </span>
            ))}
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-body p-0" style={{ maxHeight: "62vh", overflow: "auto" }}>
          <table className="table table-hover mb-0 align-middle">
            <thead className="table-dark sticky-top">
              <tr>
                <th style={{ width: "7rem" }}>Fecha</th>
                <th>Movimiento</th>
                <th>Lote</th>
                <th className="text-end">Cantidad</th>
                <th className="text-end" style={{ width: "9rem" }}>Saldo</th>
              </tr>
            </thead>
            <tbody>
              {data.resultados.map((r, i) => {
                const entrada = r.tipo === "E";
                const dia = fechaDia(r.fecha);
                const mostrarDia = dia !== diaPrevio;
                diaPrevio = dia;
                return (
                  <tr key={i}>
                    <td className="small text-body-secondary">{mostrarDia ? dia : ""}</td>
                    <td>
                      <span className={`badge ${entrada ? "text-bg-success" : "text-bg-danger"}`}>
                        <i className={`bi ${entrada ? "bi-arrow-down" : "bi-arrow-up"} me-1`} aria-hidden="true" />
                        {entrada ? "Entrada" : "Salida"}
                      </span>
                      {!entrada && r.categoria && <span className="text-body-tertiary small ms-2">{r.categoria}</span>}
                    </td>
                    <td><code className="small">{r.lote ?? "—"}</code></td>
                    <td className={`text-end fw-semibold ${entrada ? "text-success" : "text-danger"}`}>
                      {entrada ? "+" : "−"}{numero(r.cantidad)}
                    </td>
                    <td className="text-end fw-bold" style={{ fontSize: "1.1rem" }}>{numero(r.saldo)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="card-footer text-body-secondary small">Saldo acumulado por establecimiento, del más antiguo al más reciente.</div>
      </div>
    </>
  );
}

// ── Vista 2: Consumo (validación al frente) ─────────────────────────────────
function mesesDelPeriodo(periodos: string[], gran: Granularidad): number {
  if (periodos.length === 0) return 0;
  const ym = (p: string) => {
    const m = /^(\d{4})-(\d{2})/.exec(p);
    return m ? +m[1] * 12 + (+m[2] - 1) : null;
  };
  if (gran === "semana") return Math.max(1, periodos.length / 4.345);
  const nums = periodos.map(ym).filter((n): n is number => n != null);
  if (!nums.length) return periodos.length;
  return Math.max(1, Math.max(...nums) - Math.min(...nums) + 1);
}

function VistaConsumo({ data, granularidad, onGranularidad }: { data: ConsumoResponse | null; granularidad: Granularidad; onGranularidad: (g: Granularidad) => void }) {
  const max = useMemo(() => Math.max(1, ...(data?.resultados.map((r) => r.salidas) ?? [0])), [data]);
  const promedio = useMemo(() => {
    if (!data || data.resultados.length === 0) return null;
    const meses = mesesDelPeriodo(data.resultados.map((r) => r.periodo), granularidad);
    return meses > 0 ? data.total_salidas / meses : null;
  }, [data, granularidad]);

  const cpma = data?.cpma_referencia ?? null;
  const coincide = cpma != null && promedio != null && cpma > 0 ? Math.abs(cpma - promedio) / cpma <= 0.15 : null;

  return (
    <>
      {/* Validación cruzada — lo primero, grande y claro */}
      {cpma != null && promedio != null && (
        <div className="card mb-3">
          <div className="card-body">
            <div className="text-body-secondary small text-uppercase fw-semibold mb-2">
              <i className="bi bi-bullseye me-1" aria-hidden="true" />Validación cruzada del CPMA
            </div>
            <div className="row g-3 align-items-center text-center">
              <div className="col">
                <div className="text-body-secondary small">CPMA calculado</div>
                <div className="fw-bold" style={{ fontSize: "2rem", lineHeight: 1 }}>{numero(cpma)}</div>
                <div className="text-body-tertiary small">unidades / mes</div>
              </div>
              <div className="col-auto">
                <i className={`bi ${coincide ? "bi-check-circle-fill text-success" : "bi-exclamation-triangle-fill text-warning"} fs-1`} aria-hidden="true" />
              </div>
              <div className="col">
                <div className="text-body-secondary small">Consumo real (promedio)</div>
                <div className="fw-bold" style={{ fontSize: "2rem", lineHeight: 1 }}>{numero(promedio)}</div>
                <div className="text-body-tertiary small">unidades / mes</div>
              </div>
            </div>
            <div className="text-center mt-3">
              <span className={`badge ${coincide ? "text-bg-success" : "text-bg-warning"} fs-6`}>
                {coincide ? "✓ Coinciden — el CPMA cuadra con el consumo real" : "⚠ Difieren — revisar (más de 15% de diferencia)"}
              </span>
            </div>
          </div>
        </div>
      )}

      <div className="card">
        <div className="card-body">
          <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
            <GrupoPills
              label="Ver consumo por"
              incluirTodos={false}
              valor={granularidad}
              onChange={(v) => onGranularidad(v as Granularidad)}
              opciones={[{ value: "mes", label: "Mes" }, { value: "semana", label: "Semana" }, { value: "dia", label: "Día" }]}
            />
            {data && (
              <div className="text-end">
                <div className="small text-body-secondary">Consumo total en el período</div>
                <div className="fs-5 fw-bold">{numero(data.total_salidas)}</div>
              </div>
            )}
          </div>

          {!data || data.resultados.length === 0 ? (
            <div className="alert alert-secondary mb-0">Sin salidas para este producto y filtros.</div>
          ) : (
            <div className="d-flex flex-column gap-2" style={{ maxHeight: "52vh", overflow: "auto" }}>
              {data.resultados.map((r) => {
                const etiqueta = granularidad === "mes" ? mesLargo(r.periodo) : r.periodo;
                const sobreCpma = cpma != null && granularidad === "mes" && r.salidas > cpma;
                return (
                  <div key={r.periodo} className="d-flex align-items-center gap-2">
                    <span className="small text-nowrap fw-semibold" style={{ width: 88 }}>{etiqueta}</span>
                    <div className="flex-grow-1" style={{ background: "#eef1f4", borderRadius: 5, height: 24, position: "relative" }}>
                      <div style={{ width: `${(r.salidas / max) * 100}%`, height: "100%", background: sobreCpma ? "#dc3545" : "#0d6efd", borderRadius: 5, minWidth: 2 }} />
                    </div>
                    <span className="fw-semibold text-nowrap" style={{ width: 70, textAlign: "right" }}>{numero(r.salidas)}</span>
                  </div>
                );
              })}
              {granularidad === "mes" && cpma != null && (
                <div className="small text-body-secondary mt-1">
                  <span style={{ display: "inline-block", width: 10, height: 10, background: "#dc3545", borderRadius: 2 }} className="me-1" />
                  mes por encima del CPMA ({numero(cpma)}/mes)
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

// ── Vista 3: Clasificación de salidas ───────────────────────────────────────
function VistaClasificacion({ data }: { data: ClasificacionResponse | null }) {
  if (!data) return null;
  if (data.resultados.length === 0) return <div className="alert alert-secondary">Sin salidas para este producto y filtros.</div>;
  const total = data.total_salidas || 1;
  return (
    <>
      <div className="row g-3 mb-3">
        {data.resultados.map((r) => {
          const pct = (r.salidas / total) * 100;
          const color = CAT_COLOR[r.categoria] ?? "#adb5bd";
          return (
            <div className="col-6 col-lg-3" key={r.categoria}>
              <div className="card h-100" style={{ borderTop: `4px solid ${color}` }}>
                <div className="card-body py-3">
                  <div className="fw-bold" style={{ fontSize: "1.9rem", lineHeight: 1, color }}>{pct.toFixed(0)}%</div>
                  <div className="fw-semibold small mt-1">{r.categoria}</div>
                  <div className="text-body-secondary small">{numero(r.salidas)} u · {r.movimientos} mov.</div>
                </div>
              </div>
            </div>
          );
        })}
      </div>

      <div className="card">
        <div className="card-body">
          <div className="d-flex justify-content-between align-items-baseline mb-2">
            <span className="fw-semibold">Distribución de salidas por categoría</span>
            <span className="small text-body-secondary">total {numero(data.total_salidas)} unidades</span>
          </div>
          <div className="d-flex rounded overflow-hidden mb-2" style={{ height: 26 }} role="img" aria-label="Distribución de salidas por categoría">
            {data.resultados.map((r) => (
              <div
                key={r.categoria}
                title={`${r.categoria}: ${((r.salidas / total) * 100).toFixed(1)}% (${numero(r.salidas)})`}
                className="d-flex align-items-center justify-content-center text-white"
                style={{ width: `${(r.salidas / total) * 100}%`, background: CAT_COLOR[r.categoria] ?? "#adb5bd", fontSize: "0.72rem", fontWeight: 600, minWidth: (r.salidas / total) > 0.08 ? undefined : 0 }}
              >
                {(r.salidas / total) > 0.1 ? `${((r.salidas / total) * 100).toFixed(0)}%` : ""}
              </div>
            ))}
          </div>
          <p className="small text-body-secondary mb-0">
            <i className="bi bi-shield-check me-1" aria-hidden="true" />
            La categoría se deriva sin abrir al paciente; nunca se muestra el nombre, DNI ni diagnóstico.
          </p>
        </div>
      </div>
    </>
  );
}
