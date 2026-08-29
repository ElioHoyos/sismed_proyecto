import { useMemo, useState, type CSSProperties } from "react";
import type { DisponibilidadRed, Situacion } from "../services/types";
import { SITUACION_ORDEN } from "../services/situacion";
import { SituacionBadge } from "./SituacionBadge";

type FilaTablaMaestra = DisponibilidadRed;

interface Props {
  filas: FilaTablaMaestra[];
  cargando: boolean;
  error: string | null;
  /** Vista compacta: oculta los 12 meses (+ sparkline) y SUMAMES/CONTADOR. */
  compacta: boolean;
  /** "red" = Red + AEM (usa la suma → dispo_total/situacion_total, muestra ambos
   * stocks). "establecimiento" = EESS (solo stock_red → dispo/situacion). */
  vista: "red" | "establecimiento";
}

type SortKey =
  | "codigo_siga"
  | "producto_cod"
  | "producto_nombre"
  | "medtip"
  | "medpet"
  | "medest"
  | "ff"
  | "sumames"
  | "contador"
  | "cpma"
  | "stock_red"
  | "stock_aem"
  | "dispo"
  | "situacion"
  | "dispo_total"
  | "situacion_total";

type SortDir = "asc" | "desc";

const SIGNIFICADO_MEDTIP: Record<string, string> = { M: "Medicamento", I: "Insumo" };
const SIGNIFICADO_MEDPET: Record<string, string> = { P: "Petitorio", _: "SIS" };
const SITUACIONES_ALERTA: Situacion[] = ["DESABASTECIDO", "CRITICO"];

const W_SIGA = 118;
const W_MED = 264;
const ROW1_H = 33; // alto de la fila de grupos (para el sticky de la fila de columnas)
const DARK = "#212529";

function numero(valor: number, decimales = 0): string {
  return valor.toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

function valorOrden(fila: FilaTablaMaestra, key: SortKey): number | string {
  switch (key) {
    case "situacion":
      return SITUACION_ORDEN.indexOf(fila.situacion);
    case "situacion_total":
      return SITUACION_ORDEN.indexOf(fila.situacion_total);
    case "producto_cod":
    case "producto_nombre":
      return fila[key];
    case "codigo_siga":
    case "medtip":
    case "medpet":
    case "medest":
    case "ff":
      return fila[key] ?? "";
    default:
      return fila[key];
  }
}

function CeldaCodigo({ valor, significados }: { valor: string | null; significados?: Record<string, string> }) {
  if (!valor) return <td className="text-center text-body-secondary">—</td>;
  return (
    <td className="text-center" title={significados?.[valor]}>
      {valor}
    </td>
  );
}

export function TablaMaestra({ filas, cargando, error, compacta, vista }: Props) {
  const esTotal = vista === "red"; // Red + AEM → columnas de la suma
  const [sortKey, setSortKey] = useState<SortKey | null>(null);
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  function ordenarPor(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  }

  const filasOrdenadas = useMemo(() => {
    if (!sortKey) return filas;
    const arr = [...filas];
    arr.sort((a, b) => {
      const va = valorOrden(a, sortKey);
      const vb = valorOrden(b, sortKey);
      const cmp =
        typeof va === "number" && typeof vb === "number" ? va - vb : String(va).localeCompare(String(vb), "es");
      return sortDir === "asc" ? cmp : -cmp;
    });
    return arr;
  }, [filas, sortKey, sortDir]);

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        No se pudo cargar la tabla: {error}
      </div>
    );
  }

  const meses = filas[0]?.meses ?? [];

  const thTopStyle: CSSProperties = { position: "sticky", top: ROW1_H, zIndex: 3, background: DARK };
  const frozenTh = (left: number, width: number): CSSProperties => ({
    ...thTopStyle,
    left,
    minWidth: width,
    width,
    zIndex: 5,
  });
  const frozenTd = (left: number, width: number, bg: string): CSSProperties => ({
    position: "sticky",
    left,
    minWidth: width,
    width,
    zIndex: 2,
    background: bg,
  });

  function Th({
    label,
    tecnico,
    ordenarKey,
    numeric,
    frozen,
  }: {
    label: string;
    tecnico?: string;
    ordenarKey: SortKey;
    numeric?: boolean;
    frozen?: { left: number; width: number };
  }) {
    const activa = sortKey === ordenarKey;
    const style = frozen ? frozenTh(frozen.left, frozen.width) : thTopStyle;
    return (
      <th
        role="button"
        onClick={() => ordenarPor(ordenarKey)}
        title={tecnico ? `${tecnico}\n(clic para ordenar)` : "Clic para ordenar"}
        className={`user-select-none ${numeric ? "text-end" : ""}`}
        style={{ ...style, cursor: "pointer" }}
        aria-sort={activa ? (sortDir === "asc" ? "ascending" : "descending") : "none"}
      >
        {label}{" "}
        <i
          className={`bi ${activa ? (sortDir === "asc" ? "bi-caret-up-fill" : "bi-caret-down-fill") : "bi-arrow-down-up"}`}
          style={{ opacity: activa ? 1 : 0.35, fontSize: "0.75em" }}
          aria-hidden="true"
        />
      </th>
    );
  }

  const grupoStyle: CSSProperties = { position: "sticky", top: 0, zIndex: 4, background: DARK, borderLeft: "2px solid #495057" };

  return (
    <div className="card">
      <div className="card-body p-0" style={{ maxHeight: "74vh", overflow: "auto" }}>
        <table className="table table-hover text-nowrap mb-0 align-middle" style={{ fontSize: "0.85rem" }}>
          <thead>
            {/* Fila de GRUPOS */}
            <tr className="table-dark text-uppercase" style={{ fontSize: "0.7rem", letterSpacing: "0.03em" }}>
              <th colSpan={7} style={{ ...grupoStyle, borderLeft: "none" }}>Producto</th>
              {!compacta && <th colSpan={meses.length} style={grupoStyle}>Consumo · últimos 12 meses</th>}
              <th colSpan={compacta ? 1 : 3} style={grupoStyle}>Cálculo</th>
              <th colSpan={esTotal ? 4 : 3} style={grupoStyle}>
                {esTotal ? "Stock y disponibilidad · Red + AEM" : "Stock y disponibilidad · EESS"}
              </th>
            </tr>
            {/* Fila de COLUMNAS */}
            <tr className="table-dark">
              <Th label="CÓD. SIGA" tecnico="CODIGO_SIG del catálogo oficial (MPRODUCTO)" ordenarKey="codigo_siga" frozen={{ left: 0, width: W_SIGA }} />
              <Th label="Medicamento" tecnico="Nombre del medicamento" ordenarKey="producto_nombre" frozen={{ left: W_SIGA, width: W_MED }} />
              <Th label="Código" tecnico="CODIGO MEDICAMENTO" ordenarKey="producto_cod" />
              <Th label="M/I" tecnico="MEDTIP — M = Medicamento, I = Insumo" ordenarKey="medtip" />
              <Th label="_/P" tecnico="MEDPET — P = Petitorio, _ = SIS" ordenarKey="medpet" />
              <Th label="E/S/_" tecnico="MEDEST — código de estado (E / S / _)" ordenarKey="medest" />
              <Th label="FF" tecnico="Forma farmacéutica" ordenarKey="ff" />
              {!compacta &&
                meses.map((mes) => (
                  <th key={`${mes.anio}-${mes.mes}`} className="text-end" title={`Consumo de ${mes.nombre} ${mes.anio}`} style={thTopStyle}>
                    {mes.nombre.slice(0, 3)}
                  </th>
                ))}
              {!compacta && <Th label="Consumo 12m" tecnico="SUMAMES — suma del consumo de los últimos 12 meses" ordenarKey="sumames" numeric />}
              {!compacta && <Th label="Meses c/cons." tecnico="CONTADOR — nº de meses (de los 12) con consumo > 0" ordenarKey="contador" numeric />}
              <Th label="Consumo/mes" tecnico="CPMA — consumo promedio mensual" ordenarKey="cpma" numeric />
              <Th label="Stock Red" tecnico="STOCK — stock de la Red (establecimientos)" ordenarKey="stock_red" numeric />
              {esTotal && <Th label="Stock AEM" tecnico="Stock_AEM — Almacén Especializado de Medicamentos (central)" ordenarKey="stock_aem" numeric />}
              {esTotal ? (
                <>
                  <Th label="Meses (total)" tecnico="DISPO_TOTAL = (stock_red + stock_aem) / CPMA" ordenarKey="dispo_total" numeric />
                  <Th label="Situación" tecnico="Situación con Red + AEM (la suma)" ordenarKey="situacion_total" />
                </>
              ) : (
                <>
                  <Th label="Meses (EESS)" tecnico="DISPO = stock_red / CPMA (solo el establecimiento)" ordenarKey="dispo" numeric />
                  <Th label="Situación" tecnico="Situación con el stock de la Red (EESS)" ordenarKey="situacion" />
                </>
              )}
            </tr>
          </thead>
          <tbody>
            {filasOrdenadas.map((fila) => {
              const enAlerta = SITUACIONES_ALERTA.includes(fila.situacion_total);
              const bgFila = enAlerta ? "#fdECEE" : "#ffffff";
              const borde = enAlerta ? "#dc3545" : "transparent";
              return (
                <tr key={fila.producto_cod} style={enAlerta ? { backgroundColor: "rgba(220,53,69,0.05)" } : undefined}>
                  <td className="text-center" style={{ ...frozenTd(0, W_SIGA, bgFila), fontSize: "0.75rem", color: "#6c757d", boxShadow: `inset 4px 0 0 ${borde}` }}>
                    {fila.codigo_siga ?? "—"}
                  </td>
                  <td style={{ ...frozenTd(W_SIGA, W_MED, bgFila), whiteSpace: "normal", paddingTop: 10, paddingBottom: 10 }}>
                    <span className="fw-semibold" style={{ fontSize: "0.95rem" }}>
                      {fila.producto_nombre}
                    </span>
                  </td>
                  <td>{fila.producto_cod}</td>
                  <CeldaCodigo valor={fila.medtip} significados={SIGNIFICADO_MEDTIP} />
                  <CeldaCodigo valor={fila.medpet} significados={SIGNIFICADO_MEDPET} />
                  <CeldaCodigo valor={fila.medest} />
                  <CeldaCodigo valor={fila.ff} />
                  {!compacta &&
                    fila.meses.map((mes) => (
                      <td key={`${mes.anio}-${mes.mes}`} className="text-end" style={mes.consumo === 0 ? { color: "#ccd1d6" } : undefined}>
                        {numero(mes.consumo)}
                      </td>
                    ))}
                  {!compacta && <td className="text-end">{numero(fila.sumames)}</td>}
                  {!compacta && <td className="text-end">{fila.contador}</td>}
                  <td className="text-end fw-semibold">{numero(fila.cpma, 2)}</td>
                  <td className="text-end">{numero(fila.stock_red)}</td>
                  {esTotal && <td className="text-end">{numero(fila.stock_aem)}</td>}
                  {esTotal ? (
                    <>
                      <td className="text-end">{numero(fila.dispo_total, 2)}</td>
                      <td>
                        <SituacionBadge situacion={fila.situacion_total} conIcono />
                      </td>
                    </>
                  ) : (
                    <>
                      <td className="text-end">{numero(fila.dispo, 2)}</td>
                      <td>
                        <SituacionBadge situacion={fila.situacion} conIcono />
                      </td>
                    </>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>

        {cargando && (
          <div className="text-center text-body-secondary p-4">
            <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
            Cargando…
          </div>
        )}
        {!cargando && filas.length === 0 && (
          <div className="text-center text-body-secondary p-5">
            <i className="bi bi-inbox fs-2 d-block mb-2" aria-hidden="true" />
            No hay productos para estos filtros. Prueba quitar algún filtro o cambiar la búsqueda.
          </div>
        )}
      </div>
    </div>
  );
}
