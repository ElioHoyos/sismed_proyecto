import { useCallback, useEffect, useState, type ReactNode } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { GrupoPills } from "../components/filtros/GrupoPills";
import {
  marcarRevision,
  obtenerHistorial,
  obtenerHistorialResumen,
  quitarRevision,
} from "../services/api";
import type { FiltroHistorial, HistorialIncidencia, HistorialResumen } from "../services/types";

function mesActual(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}
function numero(v: number): string {
  return v.toLocaleString("es-PE", { maximumFractionDigits: 2 });
}
function fechaHora(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function HistorialPage() {
  const [estado, setEstado] = useState<FiltroHistorial>("pendientes");
  const [mes, setMes] = useState<string>(mesActual);
  const [filas, setFilas] = useState<HistorialIncidencia[]>([]);
  const [resumen, setResumen] = useState<HistorialResumen | null>(null);
  const [cargando, setCargando] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const recargar = useCallback(() => {
    let vigente = true;
    setCargando(true);
    setError(null);
    Promise.all([obtenerHistorial({ estado, mes }), obtenerHistorialResumen(mes)])
      .then(([h, r]) => {
        if (!vigente) return;
        setFilas(h.resultados);
        setResumen(r);
      })
      .catch((e: unknown) => vigente && setError(e instanceof Error ? e.message : "Error desconocido"))
      .finally(() => vigente && setCargando(false));
    return () => {
      vigente = false;
    };
  }, [estado, mes]);

  useEffect(() => recargar(), [recargar]);

  return (
    <AppLayout titulo="Historial de correcciones — stock negativo">
      <div className="alert alert-info d-flex align-items-start gap-2 py-2" role="note">
        <i className="bi bi-info-circle-fill mt-1" aria-hidden="true" />
        <span className="small">
          Cada carga del stock es una foto. El sistema compara carga contra carga y lleva la{" "}
          <strong>vida de cada negativo</strong>: cuándo apareció, cuándo se marcó revisado y cuándo se
          corrigió (dejó de ser negativo). El estado <strong>resuelto se detecta solo</strong> — aunque
          nadie marque el check. El check agrega el <em>quién lo atendió</em>.
        </span>
      </div>

      {/* Resumen mensual */}
      {resumen && (
        <div className="row g-3 mb-3">
          <TarjetaResumen titulo={`Negativos detectados en ${mes}`} valor={resumen.negativos} icono="bi-dash-circle" color="#dc3545" />
          <TarjetaResumen titulo="Resueltos (de ese mes)" valor={resumen.resueltos} icono="bi-check2-circle" color="#198754" />
          <TarjetaResumen titulo="Pendientes (de ese mes)" valor={resumen.pendientes} icono="bi-hourglass-split" color="#fd7e14" />
          <TarjetaResumen titulo="Pendientes ahora (total)" valor={resumen.pendientes_totales} icono="bi-exclamation-triangle" color="#6c757d" />
        </div>
      )}

      {/* Filtros */}
      <div className="card mb-3">
        <div className="card-body d-flex flex-wrap gap-4 align-items-end">
          <GrupoPills
            label="Ver"
            incluirTodos={false}
            valor={estado}
            onChange={(v) => setEstado(v as FiltroHistorial)}
            opciones={[
              { value: "pendientes", label: "Pendientes (ahora)" },
              { value: "resueltos", label: "Resueltos (histórico)" },
              { value: "todos", label: "Todos" },
            ]}
          />
          <div>
            <label className="form-label small mb-1 fw-semibold d-block" htmlFor="hist-mes">Mes (detección)</label>
            <input id="hist-mes" type="month" className="form-control form-control-sm" style={{ maxWidth: 180 }} value={mes} onChange={(e) => setMes(e.target.value)} />
          </div>
          <span className="text-body-secondary small ms-auto align-self-center">
            {cargando ? "Cargando…" : `${filas.length} incidencia(s)`}
          </span>
        </div>
      </div>

      {error ? (
        <div className="alert alert-danger" role="alert">No se pudo cargar el historial: {error}</div>
      ) : !cargando && filas.length === 0 ? (
        <div className="card">
          <div className="card-body text-center text-body-secondary p-5">
            <i className="bi bi-check2-circle fs-2 d-block mb-2 text-success" aria-hidden="true" />
            {estado === "pendientes"
              ? "No hay negativos pendientes. 🎉"
              : "No hay incidencias para este filtro."}
          </div>
        </div>
      ) : (
        <div className="d-flex flex-column gap-2">
          {filas.map((f) => (
            <FilaHistorial key={f.id} f={f} onCambio={recargar} />
          ))}
        </div>
      )}
    </AppLayout>
  );
}

function TarjetaResumen({ titulo, valor, icono, color }: { titulo: string; valor: number; icono: string; color: string }) {
  return (
    <div className="col-6 col-lg-3">
      <div className="card h-100" style={{ borderLeft: `4px solid ${color}` }}>
        <div className="card-body d-flex align-items-center gap-3 py-3">
          <i className={`bi ${icono} fs-3`} style={{ color }} aria-hidden="true" />
          <div>
            <div className="fs-4 fw-bold" style={{ lineHeight: 1 }}>{valor.toLocaleString("es-PE")}</div>
            <div className="text-body-secondary small">{titulo}</div>
          </div>
        </div>
      </div>
    </div>
  );
}

function Paso({ activo, icono, titulo, children }: { activo: boolean; icono: string; titulo: string; children: ReactNode }) {
  return (
    <div className="flex-fill" style={{ minWidth: 160, opacity: activo ? 1 : 0.5 }}>
      <div className="d-flex align-items-center gap-1 fw-semibold small">
        <i className={`bi ${icono}`} aria-hidden="true" />
        {titulo}
      </div>
      <div className="small text-body-secondary mt-1">{children}</div>
    </div>
  );
}

function FilaHistorial({ f, onCambio }: { f: HistorialIncidencia; onCambio: () => void }) {
  const [editando, setEditando] = useState(false);
  const [nota, setNota] = useState(f.nota ?? "");
  const [guardando, setGuardando] = useState(false);

  const resuelto = f.estado === "RESUELTO";
  const ubicacion = f.establecimiento_nombre ?? (f.almacen_cod ? `Almacén ${f.almacen_cod}` : "—");

  async function guardar() {
    setGuardando(true);
    try {
      await marcarRevision(f.id, { nota: nota.trim() || undefined });
      setEditando(false);
      onCambio();
    } finally {
      setGuardando(false);
    }
  }
  async function quitar() {
    setGuardando(true);
    try {
      await quitarRevision(f.id);
      onCambio();
    } finally {
      setGuardando(false);
    }
  }

  return (
    <div className="card" style={{ borderLeft: `4px solid ${resuelto ? "#198754" : "#dc3545"}` }}>
      <div className="card-body py-3">
        <div className="d-flex justify-content-between align-items-start gap-2 flex-wrap mb-2">
          <div>
            <span className="fw-semibold">{f.producto_nombre}</span>
            <span className="text-body-secondary small ms-2">
              lote <code>{f.lote}</code> · Cód {f.producto_cod} · SIGA {f.codigo_siga ?? "—"}
            </span>
            <div className="text-body-secondary small">
              <i className="bi bi-geo-alt me-1" aria-hidden="true" />
              {ubicacion}
            </div>
          </div>
          {resuelto ? (
            <span className="badge text-bg-success"><i className="bi bi-check-lg me-1" aria-hidden="true" />Resuelto</span>
          ) : (
            <span className="badge text-bg-danger">Pendiente · {f.dias} día{f.dias === 1 ? "" : "s"}</span>
          )}
        </div>

        {/* Línea de tiempo: detectado → revisado → resuelto */}
        <div className="d-flex flex-wrap gap-3 align-items-stretch">
          <Paso activo icono="bi-exclamation-octagon-fill text-danger" titulo="Detectado">
            <span className="fw-bold text-danger">{numero(f.valor_detectado)}</span> · {fechaHora(f.detectado_en)}
            {!resuelto && f.valor_actual !== f.valor_detectado && (
              <span> · ahora {numero(f.valor_actual)}</span>
            )}
            {f.detectado_inicial && (
              <span
                className="badge text-bg-light border ms-2"
                title="Ya existía cuando arrancó el motor; la fecha es la del sembrado, no el momento real en que apareció"
              >
                carga inicial
              </span>
            )}
          </Paso>

          <i className="bi bi-arrow-right text-body-tertiary align-self-center d-none d-md-block" aria-hidden="true" />

          <Paso activo={f.revisado} icono={f.revisado ? "bi-person-check-fill text-primary" : "bi-person"} titulo="Revisado">
            {f.revisado ? (
              <>
                {f.revisado_por ? `${f.revisado_por} · ` : ""}{fechaHora(f.revisado_en)}
                {f.nota && <div className="fst-italic">“{f.nota}”</div>}
                <button type="button" className="btn btn-link btn-sm p-0 text-secondary" onClick={quitar} disabled={guardando}>
                  quitar
                </button>
              </>
            ) : editando ? (
              <div className="d-flex flex-column gap-1 mt-1" style={{ maxWidth: 240 }}>
                <input className="form-control form-control-sm" placeholder="Nota (opcional, ej. corregido en SISMED)" value={nota} onChange={(e) => setNota(e.target.value)} autoFocus />
                <div className="d-flex gap-1">
                  <button type="button" className="btn btn-primary btn-sm" onClick={guardar} disabled={guardando}>Marcar revisado</button>
                  <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => setEditando(false)} disabled={guardando}>Cancelar</button>
                </div>
              </div>
            ) : (
              <button type="button" className="btn btn-outline-primary btn-sm mt-1" onClick={() => setEditando(true)}>
                <i className="bi bi-check2-square me-1" aria-hidden="true" />
                Marcar revisado
              </button>
            )}
          </Paso>

          <i className="bi bi-arrow-right text-body-tertiary align-self-center d-none d-md-block" aria-hidden="true" />

          <Paso activo={resuelto} icono={resuelto ? "bi-check-circle-fill text-success" : "bi-hourglass"} titulo="Resuelto">
            {resuelto ? (
              <>
                <span className="fw-bold text-success">{numero(f.valor_resuelto ?? 0)}</span> · {fechaHora(f.resuelto_en)}
              </>
            ) : (
              <span>Aún negativo</span>
            )}
          </Paso>
        </div>
      </div>
    </div>
  );
}
