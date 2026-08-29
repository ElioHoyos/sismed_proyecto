import { useState } from "react";
import { marcarRevision, quitarRevision } from "../services/api";

interface Props {
  incidenciaId: number | null;
  revisado: boolean;
  revisadoEn: string | null;
  nota: string | null;
  /** Reconsulta el stock para reflejar el cambio (mismo dato que el Historial). */
  onCambio: () => void;
}

function fechaHora(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("es-PE", { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

/** Check "revisado/corregido en SISMED" para un lote negativo, desde la pantalla
 * de Stock. Escribe en la misma tabla revision_stock que el Historial: marcar
 * aquí se ve allá y viceversa. Sin campo "quién" (aún no hay login); solo check
 * + nota opcional, con fecha automática. */
export function ControlRevisionStock({ incidenciaId, revisado, revisadoEn, nota, onCambio }: Props) {
  const [abierto, setAbierto] = useState(false);
  const [notaInput, setNotaInput] = useState("");
  const [guardando, setGuardando] = useState(false);

  if (incidenciaId == null) return null; // aparece tras la carga que la registró

  async function guardar() {
    setGuardando(true);
    try {
      await marcarRevision(incidenciaId!, { nota: notaInput.trim() || undefined });
      setAbierto(false);
      setNotaInput("");
      onCambio();
    } finally {
      setGuardando(false);
    }
  }
  async function quitar() {
    setGuardando(true);
    try {
      await quitarRevision(incidenciaId!);
      onCambio();
    } finally {
      setGuardando(false);
    }
  }

  if (revisado) {
    return (
      <div className="small text-success mt-1">
        <span className="d-inline-flex align-items-center gap-1">
          <i className="bi bi-check-circle-fill" aria-hidden="true" />
          Revisado/corregido
          {revisadoEn && <span className="text-body-secondary">· {fechaHora(revisadoEn)}</span>}
          <button type="button" className="btn btn-link btn-sm p-0 ms-1 text-secondary" onClick={quitar} disabled={guardando}>
            quitar
          </button>
        </span>
        {nota && <div className="text-body-secondary fst-italic">“{nota}”</div>}
      </div>
    );
  }

  if (!abierto) {
    return (
      <div className="form-check mt-1">
        <input
          className="form-check-input"
          type="checkbox"
          id={`rev-${incidenciaId}`}
          checked={false}
          onChange={() => setAbierto(true)}
          disabled={guardando}
        />
        <label className="form-check-label small text-body-secondary" htmlFor={`rev-${incidenciaId}`}>
          Revisado/corregido en SISMED
        </label>
      </div>
    );
  }

  return (
    <div className="mt-1 d-flex flex-column gap-1" style={{ maxWidth: 220 }}>
      <input
        className="form-control form-control-sm"
        placeholder="Nota (opcional, ej. corregido en SISMED)"
        value={notaInput}
        onChange={(e) => setNotaInput(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") guardar();
        }}
        autoFocus
      />
      <div className="d-flex gap-1">
        <button type="button" className="btn btn-primary btn-sm" onClick={guardar} disabled={guardando}>
          Marcar revisado
        </button>
        <button type="button" className="btn btn-outline-secondary btn-sm" onClick={() => setAbierto(false)} disabled={guardando}>
          Cancelar
        </button>
      </div>
    </div>
  );
}
