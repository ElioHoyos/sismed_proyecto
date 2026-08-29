import type { Situacion, Vista } from "../services/types";
import { SITUACION_META, SITUACION_ORDEN } from "../services/situacion";
import { OPCIONES_FINANCIAMIENTO, OPCIONES_MEDEST, OPCIONES_TIPO } from "../services/clasificacion";
import { GrupoPills } from "./filtros/GrupoPills";
import { SelectorBuscable } from "./filtros/SelectorBuscable";

export interface EstablecimientoOpcion {
  cod: string;
  nombre: string;
}

interface Props {
  vista: Vista;
  onVistaChange: (vista: Vista) => void;
  periodo: string;
  onPeriodoChange: (periodo: string) => void;
  establecimientos: EstablecimientoOpcion[];
  establecimientoCod: string;
  onEstablecimientoChange: (cod: string) => void;
  situacionFiltro: Situacion | "";
  onSituacionChange: (situacion: Situacion | "") => void;
  tipoFiltro: string;
  onTipoChange: (tipo: string) => void;
  petitorioFiltro: string;
  onPetitorioChange: (financiamiento: string) => void;
  medestFiltro: string;
  onMedestChange: (medest: string) => void;
  busqueda: string;
  onBusquedaChange: (busqueda: string) => void;
  vistaCompacta: boolean;
  onVistaCompactaChange: (v: boolean) => void;
}

const SITUACION_PILLS = SITUACION_ORDEN.map((s) => ({
  value: s,
  label: SITUACION_META[s].label,
  color: SITUACION_META[s].color,
}));

export function FiltrosBarra({
  vista,
  onVistaChange,
  periodo,
  onPeriodoChange,
  establecimientos,
  establecimientoCod,
  onEstablecimientoChange,
  situacionFiltro,
  onSituacionChange,
  tipoFiltro,
  onTipoChange,
  petitorioFiltro,
  onPetitorioChange,
  medestFiltro,
  onMedestChange,
  busqueda,
  onBusquedaChange,
  vistaCompacta,
  onVistaCompactaChange,
}: Props) {
  return (
    <div className="card mb-2">
      <div className="card-body d-flex flex-wrap gap-4">
        <GrupoPills
          label="Vista"
          incluirTodos={false}
          valor={vista}
          onChange={(v) => onVistaChange(v as Vista)}
          opciones={[
            { value: "red", label: "Red + AEM (consolidada)" },
            { value: "establecimiento", label: "EESS (por establecimiento)" },
          ]}
        />

        {vista === "establecimiento" && (
          <div style={{ minWidth: 240 }}>
            <SelectorBuscable
              label="Establecimiento"
              opciones={establecimientos.map((e) => ({ value: e.cod, label: e.nombre }))}
              valor={establecimientoCod}
              onChange={onEstablecimientoChange}
              placeholder="Buscar establecimiento…"
              etiquetaTodos="— Selecciona —"
            />
          </div>
        )}

        <div>
          <label className="form-label mb-1 d-block" htmlFor="filtro-periodo">
            Periodo
          </label>
          <input
            id="filtro-periodo"
            type="month"
            className="form-control form-control-sm"
            style={{ width: 160 }}
            value={periodo}
            onChange={(e) => onPeriodoChange(e.target.value)}
          />
        </div>

        <GrupoPills
          label="Situación"
          etiquetaTodos="Todas"
          valor={situacionFiltro}
          onChange={(v) => onSituacionChange(v as Situacion | "")}
          opciones={SITUACION_PILLS}
        />

        <GrupoPills label="Tipo (M/I)" valor={tipoFiltro} onChange={onTipoChange} opciones={OPCIONES_TIPO} />

        <GrupoPills
          label="Financiamiento (_/P)"
          valor={petitorioFiltro}
          onChange={onPetitorioChange}
          opciones={OPCIONES_FINANCIAMIENTO}
        />

        <GrupoPills label="MEDEST (E/S/_)" valor={medestFiltro} onChange={onMedestChange} opciones={OPCIONES_MEDEST} />

        <div style={{ flex: "1 1 240px", minWidth: 220 }}>
          <label className="form-label mb-1 d-block" htmlFor="filtro-busqueda">
            Buscar
          </label>
          <div className="input-group input-group-sm">
            <span className="input-group-text">
              <i className="bi bi-search" aria-hidden="true" />
            </span>
            <input
              id="filtro-busqueda"
              type="search"
              className="form-control"
              placeholder="Nombre o código del medicamento…"
              value={busqueda}
              onChange={(e) => onBusquedaChange(e.target.value)}
            />
          </div>
        </div>

        <div className="align-self-end">
          <div className="form-check form-switch">
            <input
              id="vista-compacta"
              className="form-check-input"
              type="checkbox"
              role="switch"
              checked={vistaCompacta}
              onChange={(e) => onVistaCompactaChange(e.target.checked)}
            />
            <label className="form-check-label" htmlFor="vista-compacta">
              Vista compacta
            </label>
          </div>
        </div>
      </div>
    </div>
  );
}
