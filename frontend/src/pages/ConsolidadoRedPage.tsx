import { useEffect, useRef, useState } from "react";
import { AppLayout } from "../components/layout/AppLayout";
import { BotonExportar } from "../components/BotonExportar";
import { ConsolidadoTabla } from "../components/ConsolidadoTabla";
import { useConsolidado } from "../hooks/useConsolidado";
import { descargarExport, guardarEdicionCompra, revertirEdicionCompra } from "../services/api";
import type { CampoEditableCompra, ConsolidadoRow } from "../services/types";

type EstadoGuardado = { tipo: "guardando" } | { tipo: "ok" } | { tipo: "error"; msg: string } | null;

export function ConsolidadoRedPage() {
  const [periodoInput, setPeriodoInput] = useState<string>("");
  const [compraAnioSel, setCompraAnioSel] = useState<number | undefined>();
  const [guardado, setGuardado] = useState<EstadoGuardado>(null);
  const timerOk = useRef<number | undefined>(undefined);

  const { cargando, error, periodo, compraAnio, aniosCompra, filas, recargar, aplicarEdicionLocal } = useConsolidado(
    periodoInput || undefined,
    compraAnioSel,
  );

  // Lo confirmado por el backend (no lo que el usuario tecleó a medias).
  const periodoConfirmado = periodo ?? "";
  const anioConfirmado = compraAnio;

  // El "Guardado ✓" se oculta solo tras un momento; el error se mantiene.
  useEffect(() => {
    if (guardado?.tipo === "ok") {
      timerOk.current = window.setTimeout(() => setGuardado(null), 1600);
      return () => window.clearTimeout(timerOk.current);
    }
  }, [guardado]);

  async function editar(row: ConsolidadoRow, campo: CampoEditableCompra, valor: string | null) {
    if (anioConfirmado == null) return;
    const esRevertir = valor === null;
    // Optimista: se ve al instante y no se pierde lo escrito si el guardado falla.
    aplicarEdicionLocal(row.producto_cod, campo, valor);
    setGuardado({ tipo: "guardando" });
    try {
      if (esRevertir) {
        await revertirEdicionCompra({ anio: anioConfirmado, codigo_sismed: row.producto_cod, campo });
        recargar(); // al revertir, traer el valor real del archivo
      } else {
        await guardarEdicionCompra({ anio: anioConfirmado, codigo_sismed: row.producto_cod, campo, valor });
      }
      setGuardado({ tipo: "ok" });
    } catch (e) {
      // Se conserva el valor optimista en pantalla (no se pierde lo escrito).
      setGuardado({ tipo: "error", msg: e instanceof Error ? e.message : "Error al guardar" });
    }
  }

  function exportar(formato: "xlsx" | "pdf") {
    return descargarExport("/api/consolidado-red/export", {
      formato,
      periodo: periodoConfirmado || undefined,
      compra_anio: anioConfirmado ?? undefined,
    });
  }

  const sinCompra = !cargando && aniosCompra.length === 0;

  return (
    <AppLayout titulo={`Consolidado de Red (periodo ${periodoConfirmado || "…"})`}>
      <div className="alert alert-info d-flex align-items-start gap-2 py-2 small" role="note">
        <i className="bi bi-info-circle-fill mt-1" aria-hidden="true" />
        <span>
          Vista consolidada de toda la red (Red + almacén central) cruzada automáticamente con el estado
          de compra de CENARES por Código SISMED. Reemplaza el cruce manual del <em>DISPO_RED…ConCompra</em>.
          Todo el bloque "Estado compra" se edita haciendo <strong>clic directo en la celda</strong>
          (<kbd>Enter</kbd> guarda, <kbd>Esc</kbd> cancela, <kbd>Tab</kbd> salta a la siguiente). Las
          ediciones se guardan solas, aparte del archivo, y no se pierden al reimportar el CENARES.
        </span>
      </div>

      <div className="card mb-3">
        <div className="card-body d-flex flex-wrap align-items-end gap-3">
          <div>
            <label className="form-label small mb-1 fw-semibold">Periodo</label>
            <input
              type="month"
              className="form-control form-control-sm"
              style={{ maxWidth: 180 }}
              value={periodoInput}
              onChange={(e) => setPeriodoInput(e.target.value)}
            />
          </div>

          <div>
            <label className="form-label small mb-1 fw-semibold d-block">Estado compra CENARES (año)</label>
            <div className="btn-group btn-group-sm" role="group" aria-label="Año de compra">
              {aniosCompra.length === 0 ? (
                <span className="text-body-secondary small">— sin datos de CENARES —</span>
              ) : (
                aniosCompra.map((a) => (
                  <button
                    key={a}
                    type="button"
                    className={`btn ${a === anioConfirmado ? "btn-primary" : "btn-outline-primary"}`}
                    onClick={() => setCompraAnioSel(a)}
                  >
                    {a}
                  </button>
                ))
              )}
            </div>
          </div>

          <div className="ms-auto d-flex align-items-end gap-2">
            <span className="text-body-secondary small">
              {cargando ? "Cargando…" : `${filas.length} ${filas.length === 1 ? "producto" : "productos"}`}
            </span>
            <BotonExportar onExportar={exportar} deshabilitado={filas.length === 0} />
          </div>
        </div>
      </div>

      {sinCompra && (
        <div className="alert alert-warning d-flex align-items-start gap-2 py-2 small" role="alert">
          <i className="bi bi-exclamation-triangle-fill mt-1" aria-hidden="true" />
          <span>
            Aún no hay ningún archivo de CENARES cargado. El bloque "Estado compra" aparecerá como
            <strong> "Sin compra centralizada"</strong> hasta que subas el archivo en <em>Carga de archivos</em>.
          </span>
        </div>
      )}

      <ConsolidadoTabla
        filas={filas}
        cargando={cargando}
        error={error}
        compraAnio={anioConfirmado}
        onEditar={editar}
      />

      {/* Indicador de guardado (esquina inferior derecha) */}
      {guardado && (
        <div
          className="position-fixed bottom-0 end-0 m-3"
          style={{ zIndex: 1080 }}
          role="status"
          aria-live="polite"
        >
          {guardado.tipo === "guardando" && (
            <div className="alert alert-secondary shadow-sm d-flex align-items-center gap-2 py-2 px-3 mb-0">
              <span className="spinner-border spinner-border-sm" aria-hidden="true" />
              Guardando…
            </div>
          )}
          {guardado.tipo === "ok" && (
            <div className="alert alert-success shadow-sm d-flex align-items-center gap-2 py-2 px-3 mb-0">
              <i className="bi bi-check-circle-fill" aria-hidden="true" />
              Guardado
            </div>
          )}
          {guardado.tipo === "error" && (
            <div className="alert alert-danger shadow-sm d-flex align-items-start gap-2 py-2 px-3 mb-0" style={{ maxWidth: 360 }}>
              <i className="bi bi-exclamation-triangle-fill mt-1" aria-hidden="true" />
              <div>
                <div className="fw-semibold">No se pudo guardar</div>
                <div className="small">{guardado.msg}. Tu texto sigue en la celda; vuelve a intentarlo.</div>
              </div>
              <button
                type="button"
                className="btn-close ms-2"
                aria-label="Cerrar"
                onClick={() => setGuardado(null)}
              />
            </div>
          )}
        </div>
      )}
    </AppLayout>
  );
}
