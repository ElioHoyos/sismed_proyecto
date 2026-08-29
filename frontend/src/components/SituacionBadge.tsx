import type { Situacion } from "../services/types";
import { SITUACION_META } from "../services/situacion";

interface Props {
  situacion: Situacion;
  /** Muestra el icono junto al texto (útil fuera de la tabla). */
  conIcono?: boolean;
}

export function SituacionBadge({ situacion, conIcono = false }: Props) {
  const meta = SITUACION_META[situacion];
  return (
    <span
      className="badge d-inline-flex align-items-center gap-1"
      style={{ backgroundColor: meta.color, color: meta.textoOscuro ? "#000" : "#fff" }}
      title={meta.descripcion}
    >
      {conIcono && <i className={`bi ${meta.icono}`} aria-hidden="true" />}
      {meta.label}
    </span>
  );
}
