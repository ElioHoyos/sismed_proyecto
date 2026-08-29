import type { Situacion, SituacionResumenItem } from "../services/types";
import { SITUACION_META, SITUACION_ORDEN } from "../services/situacion";

interface Props {
  cargando: boolean;
  error: string | null;
  totalSoporte: number;
  totalSis: number;
  soporte: SituacionResumenItem[];
  sis: SituacionResumenItem[];
  situacionActiva: Situacion | "";
  onSituacionSelect: (situacion: Situacion) => void;
}

function ordenar(items: SituacionResumenItem[]): SituacionResumenItem[] {
  const mapa = new Map(items.map((i) => [i.situacion, i]));
  return SITUACION_ORDEN.map((s) => mapa.get(s)).filter((i): i is SituacionResumenItem => Boolean(i));
}

function Indicador({
  titulo,
  total,
  items,
  situacionActiva,
  onSituacionSelect,
}: {
  titulo: string;
  total: number;
  items: SituacionResumenItem[];
  situacionActiva: Situacion | "";
  onSituacionSelect: (s: Situacion) => void;
}) {
  const orden = ordenar(items);
  return (
    <div className="col-12 col-xl-6">
      <div className="fw-semibold mb-2">
        {titulo} <span className="text-body-secondary">· {total} productos</span>
      </div>

      <div className="d-flex rounded overflow-hidden mb-2" style={{ height: 14 }} role="img" aria-label={`Distribución ${titulo}`}>
        {orden.map((item) => {
          const meta = SITUACION_META[item.situacion];
          const atenuada = situacionActiva !== "" && situacionActiva !== item.situacion;
          return (
            <div
              key={item.situacion}
              title={`${meta.label}: ${item.porcentaje}% (${item.cantidad})`}
              onClick={() => onSituacionSelect(item.situacion)}
              style={{ width: `${item.porcentaje}%`, backgroundColor: meta.color, cursor: "pointer", opacity: atenuada ? 0.3 : 1 }}
            />
          );
        })}
      </div>

      <div className="d-flex flex-wrap gap-1">
        {orden.map((item) => {
          const meta = SITUACION_META[item.situacion];
          const activa = situacionActiva === item.situacion;
          const atenuada = situacionActiva !== "" && !activa;
          return (
            <button
              key={item.situacion}
              type="button"
              onClick={() => onSituacionSelect(item.situacion)}
              title={meta.descripcion}
              aria-pressed={activa}
              className="btn btn-sm d-inline-flex align-items-center gap-1"
              style={{
                borderWidth: 2,
                borderStyle: "solid",
                borderColor: meta.color,
                backgroundColor: activa ? meta.color : "transparent",
                color: activa ? (meta.textoOscuro ? "#000" : "#fff") : undefined,
                opacity: atenuada ? 0.5 : 1,
                fontSize: "0.78rem",
              }}
            >
              <i className={`bi ${meta.icono}`} style={{ color: activa ? "inherit" : meta.color }} aria-hidden="true" />
              <span className="fw-semibold">{meta.label}</span>
              <strong>{item.porcentaje}%</strong>
              <span className={activa ? "" : "text-body-secondary"}>({item.cantidad})</span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function ResumenSituacionRed({
  cargando,
  error,
  totalSoporte,
  totalSis,
  soporte,
  sis,
  situacionActiva,
  onSituacionSelect,
}: Props) {
  if (error) {
    return (
      <div className="alert alert-danger mb-3" role="alert">
        No se pudo cargar el resumen de situación de la red: {error}
      </div>
    );
  }

  return (
    <div className="card mb-3" aria-busy={cargando}>
      <div className="card-body">
        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <span className="fw-semibold">
            Situación de la red
            <span className="text-body-secondary"> · dos indicadores por MEDEST (Estratégicos excluidos)</span>
          </span>
          {situacionActiva && (
            <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => onSituacionSelect(situacionActiva)}>
              <i className="bi bi-x-lg me-1" aria-hidden="true" />
              Quitar filtro
            </button>
          )}
        </div>

        <div className="row g-4">
          <Indicador titulo="Soporte (S)" total={totalSoporte} items={soporte} situacionActiva={situacionActiva} onSituacionSelect={onSituacionSelect} />
          <Indicador titulo="SIS (_)" total={totalSis} items={sis} situacionActiva={situacionActiva} onSituacionSelect={onSituacionSelect} />
        </div>

        <details className="mt-3">
          <summary className="text-body-secondary small" style={{ cursor: "pointer" }}>
            ¿Qué significa cada estado?
          </summary>
          <ul className="small text-body-secondary mt-2 mb-0 ps-3">
            {SITUACION_ORDEN.map((s) => (
              <li key={s}>
                <strong style={{ color: SITUACION_META[s].color }}>{SITUACION_META[s].label}:</strong>{" "}
                {SITUACION_META[s].descripcion}
              </li>
            ))}
          </ul>
        </details>
      </div>
    </div>
  );
}
