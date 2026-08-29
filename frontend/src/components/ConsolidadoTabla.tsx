import { useEffect, useMemo, useRef, useState, type CSSProperties, type MutableRefObject } from "react";
import type { CampoEditableCompra, ConsolidadoRow } from "../services/types";
import { SituacionBadge } from "./SituacionBadge";

interface Props {
  filas: ConsolidadoRow[];
  cargando: boolean;
  error: string | null;
  compraAnio: number | null;
  /** Guarda la edición de un campo del bloque de compra (valor null = revertir). */
  onEditar: (row: ConsolidadoRow, campo: CampoEditableCompra, valor: string | null) => Promise<void>;
}

const W_SIGA = 110;
const W_MED = 250;
const ROW1_H = 34; // alto de la fila de grupos (para el sticky de la fila de columnas)
const DARK = "#212529";
const BG_EDITADO = "#fff3cd"; // amarillo suave: celda editada por el doc

type TipoCelda = "texto" | "largo" | "sugerencias" | "fecha" | "entrega";

interface DefEditable {
  campo: CampoEditableCompra;
  titulo: string;
  tecnico: string;
  tipo: TipoCelda;
  ancho: number;
  opciones?: string[];
}

/** Valores reales de ESTADO en el archivo del doc (permite además texto libre). */
const ESTADOS = [
  "Convocado",
  "Contratado",
  "No adquirido",
  "Desierto",
  "Actuaciones preparatorias",
  "Adjudicado",
  "Atención con stock de CENARES",
  "Apelado",
  "Consentido",
];

/** Las 11 columnas editables del bloque CENARES, en orden (TIPO PRODUCTO queda
 * como solo lectura y va aparte). El orden define la navegación con Tab. */
const EDITABLES: DefEditable[] = [
  { campo: "procedimiento", titulo: "Procedimiento", tecnico: "F — Procedimiento", tipo: "texto", ancho: 170 },
  { campo: "estado_situacion", titulo: "Estado", tecnico: "G — Estado situacional", tipo: "sugerencias", ancho: 180, opciones: ESTADOS },
  { campo: "observacion_estado", titulo: "Obs. estado", tecnico: "H — Observación del estado", tipo: "largo", ancho: 220 },
  { campo: "reg_siga_situacion", titulo: "Reg. SIGA situación", tecnico: "I — Registro SIGA (Situación)", tipo: "sugerencias", ancho: 170 },
  { campo: "reg_siga_observacion", titulo: "Reg. SIGA observación", tecnico: "J — Registro SIGA (Observación)", tipo: "texto", ancho: 180 },
  { campo: "contratista", titulo: "Contratista", tecnico: "K — Contratista", tipo: "texto", ancho: 190 },
  { campo: "nro_contrato", titulo: "Nro contrato", tecnico: "L — Nº de contrato", tipo: "texto", ancho: 130 },
  { campo: "fecha_convocatoria", titulo: "F. conv.", tecnico: "M — Convocatoria (fecha real)", tipo: "fecha", ancho: 120 },
  { campo: "fecha_buena_pro", titulo: "F. BP", tecnico: "N — Buena Pro (fecha real)", tipo: "fecha", ancho: 120 },
  { campo: "fecha_entrega_texto", titulo: "F. entrega", tecnico: "O — Entrega estimada (fecha exacta o mes)", tipo: "entrega", ancho: 150 },
  { campo: "observacion", titulo: "Observación", tecnico: "P — Observación", tipo: "largo", ancho: 220 },
];

const DL_ESTADO = "dl-consol-estado";
const DL_REGSIGA = "dl-consol-regsiga";

function numero(valor: number, decimales = 0): string {
  return valor.toLocaleString("es-PE", { minimumFractionDigits: decimales, maximumFractionDigits: decimales });
}

const MESES = [
  "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO",
  "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE",
];

/** F.CONV/F.BP se muestran siempre como fecha DD/MM/AAAA (guardadas en ISO). */
function fechaOTexto(v: string | null): string {
  if (!v) return "";
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : v;
}

/** Valor de un <input type="date"> (yyyy-mm-dd) a partir de ISO o DD/MM/AAAA. */
function aISO(v: string): string {
  if (!v) return "";
  const iso = /^(\d{4})-(\d{2})-(\d{2})/.exec(v);
  if (iso) return `${iso[1]}-${iso[2]}-${iso[3]}`;
  const dmy = /^(\d{2})\/(\d{2})\/(\d{4})/.exec(v);
  if (dmy) return `${dmy[3]}-${dmy[2]}-${dmy[1]}`;
  return "";
}

/** ISO (yyyy-mm-dd) → DD/MM/AAAA (formato con que el importador guarda las fechas). */
function ddmmaaaa(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** "2026-11" → "NOVIEMBRE 2026" (texto de mes estimado, como en el archivo). */
function mesTexto(ym: string): string {
  const m = /^(\d{4})-(\d{2})/.exec(ym);
  if (!m) return ym;
  return `${MESES[parseInt(m[2], 10) - 1] ?? ""} ${m[1]}`.trim();
}

/** Valor para prefijar un <input type="month"> desde una fecha o texto de mes. */
function aMesInput(v: string): string {
  if (!v) return "";
  const iso = aISO(v);
  if (iso) return iso.slice(0, 7);
  const m = /([A-ZÁÉÍÓÚ]+)\s+(\d{4})/.exec(v.trim().toUpperCase());
  if (m) {
    const idx = MESES.indexOf(m[1].replace("SETIEMBRE", "SEPTIEMBRE"));
    if (idx >= 0) return `${m[2]}-${String(idx + 1).padStart(2, "0")}`;
  }
  return "";
}

const CAMPOS_FECHA: CampoEditableCompra[] = ["fecha_convocatoria", "fecha_buena_pro"];

// ── Celda editable inline ────────────────────────────────────────────────────

interface CeldaProps {
  def: DefEditable;
  valor: string | null;
  editado: boolean;
  /** Texto tenue cuando está vacía (ej. "Sin compra centralizada" en ESTADO). */
  placeholder?: string;
  activo: boolean;
  navRef: MutableRefObject<boolean>;
  onActivar: () => void;
  onCerrar: () => void;
  onMover: (delta: number) => void;
  /** Guarda el valor (null = revertir al valor del archivo). */
  onGuardar: (valor: string | null) => void;
}

function CeldaEditable({ def, valor, editado, placeholder, activo, navRef, onActivar, onCerrar, onMover, onGuardar }: CeldaProps) {
  const [borrador, setBorrador] = useState("");
  const txtRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (activo) {
      setBorrador(valor ?? "");
      navRef.current = false; // esta celda toma el foco → su blur debe guardar
    }
  }, [activo]); // eslint-disable-line react-hooks/exhaustive-deps

  function commitCon(valorLimpio: string) {
    if (valorLimpio === (valor ?? "")) return; // sin cambios
    onGuardar(valorLimpio === "" ? null : valorLimpio);
  }
  function commit() {
    commitCon(borrador.trim());
  }

  function alTeclado(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      onCerrar(); // cancela: descarta el borrador
    } else if (e.key === "Tab") {
      e.preventDefault();
      commit();
      onMover(e.shiftKey ? -1 : 1);
    } else if (e.key === "Enter" && (def.tipo !== "largo" || e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      commit();
      onCerrar();
    }
  }

  function alPerderFoco() {
    if (navRef.current) return; // salida por teclado ya gestionada
    commit();
    onCerrar();
  }

  // Para el editor compuesto de F.ENTREGA: no cerrar mientras el foco siga
  // dentro de la celda (al pasar del texto al selector de mes/día).
  function alPerderFocoCaja(e: React.FocusEvent<HTMLDivElement>) {
    if (e.currentTarget.contains(e.relatedTarget as Node | null)) return;
    alPerderFoco();
  }

  const bg = editado ? BG_EDITADO : undefined;
  const styleTd: CSSProperties = { minWidth: def.ancho, maxWidth: def.ancho + 60, whiteSpace: "normal", background: bg, verticalAlign: "top" };

  if (activo) {
    // F.CONV / F.BP: siempre fecha real → selector de fecha (guarda ISO).
    if (def.tipo === "fecha") {
      return (
        <td style={styleTd}>
          <input
            autoFocus
            type="date"
            className="form-control form-control-sm"
            value={aISO(borrador)}
            onChange={(e) => setBorrador(e.target.value)}
            onKeyDown={alTeclado}
            onBlur={alPerderFoco}
          />
        </td>
      );
    }
    // F.ENTREGA: mixta → texto libre + selector de MES/AÑO + selector de día.
    if (def.tipo === "entrega") {
      return (
        <td style={styleTd}>
          <div onKeyDown={alTeclado} onBlur={alPerderFocoCaja}>
            <input
              ref={txtRef}
              autoFocus
              type="text"
              className="form-control form-control-sm"
              placeholder="Fecha exacta o mes (ej. NOVIEMBRE 2026)"
              value={borrador}
              onChange={(e) => setBorrador(e.target.value)}
            />
            <div className="d-flex gap-1 mt-1">
              <input
                type="month"
                className="form-control form-control-sm"
                style={{ maxWidth: 128 }}
                title="Elegir mes y año (entrega estimada)"
                value={aMesInput(borrador)}
                onChange={(e) => {
                  if (e.target.value) {
                    setBorrador(mesTexto(e.target.value));
                    txtRef.current?.focus();
                  }
                }}
              />
              <input
                type="date"
                className="form-control form-control-sm"
                style={{ maxWidth: 138 }}
                title="Elegir fecha exacta"
                value={aISO(borrador)}
                onChange={(e) => {
                  if (e.target.value) {
                    setBorrador(ddmmaaaa(e.target.value));
                    txtRef.current?.focus();
                  }
                }}
              />
            </div>
            <div className="form-text lh-sm mt-1" style={{ fontSize: "0.66rem" }}>
              Mes estimado o día exacto
            </div>
          </div>
        </td>
      );
    }
    // Texto / texto largo / sugerencias.
    const comun = {
      autoFocus: true,
      className: "form-control form-control-sm",
      value: borrador,
      onChange: (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setBorrador(e.target.value),
      onKeyDown: alTeclado,
      onBlur: alPerderFoco,
    };
    return (
      <td style={styleTd}>
        {def.tipo === "largo" ? (
          <textarea {...comun} rows={Math.min(8, Math.max(2, Math.ceil((borrador.length || 1) / 38)))} style={{ resize: "vertical" }} />
        ) : def.tipo === "sugerencias" ? (
          <input {...comun} type="text" list={def.campo === "estado_situacion" ? DL_ESTADO : DL_REGSIGA} />
        ) : (
          <input {...comun} type="text" />
        )}
      </td>
    );
  }

  const mostrado = CAMPOS_FECHA.includes(def.campo) ? fechaOTexto(valor) : valor ?? "";
  return (
    <td
      className="celda-editable"
      style={styleTd}
      role="button"
      tabIndex={0}
      title={editado ? `${def.tecnico}\nEditado por el doc — clic para cambiar` : `${def.tecnico}\nClic para editar`}
      onClick={onActivar}
      onKeyDown={(e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          onActivar();
        }
      }}
    >
      <span className="d-inline-flex align-items-start gap-1 w-100">
        <span className="flex-grow-1">
          {mostrado ? (
            mostrado
          ) : (
            <span className="text-body-tertiary fst-italic">{placeholder ?? "(vacío)"}</span>
          )}
        </span>
        {editado && (
          <button
            type="button"
            className="btn btn-link btn-sm p-0 text-secondary lh-1"
            title="Revertir al valor del archivo"
            onClick={(e) => {
              e.stopPropagation();
              onGuardar(null);
            }}
          >
            <i className="bi bi-arrow-counterclockwise" aria-hidden="true" />
          </button>
        )}
      </span>
    </td>
  );
}

// ── Tabla ───────────────────────────────────────────────────────────────────

export function ConsolidadoTabla({ filas, cargando, error, compraAnio, onEditar }: Props) {
  const [edit, setEdit] = useState<{ cod: string; idx: number } | null>(null);
  const navRef = useRef(false);

  // Sugerencias del desplegable "Reg. SIGA situación": los valores ya presentes.
  const opcionesRegSiga = useMemo(() => {
    const s = new Set<string>();
    for (const f of filas) {
      const v = f.compra.reg_siga_situacion;
      if (v) s.add(v);
    }
    return [...s].sort((a, b) => a.localeCompare(b, "es"));
  }, [filas]);

  function moverDesde(cod: string, idx: number, delta: number) {
    navRef.current = true;
    const next = idx + delta;
    setEdit(next < 0 || next >= EDITABLES.length ? null : { cod, idx: next });
  }
  function cerrar() {
    navRef.current = true;
    setEdit(null);
  }
  function activar(cod: string, idx: number) {
    navRef.current = false;
    setEdit({ cod, idx });
  }

  if (error) {
    return (
      <div className="alert alert-danger" role="alert">
        No se pudo cargar el consolidado: {error}
      </div>
    );
  }

  const meses = filas[0]?.meses ?? [];
  const nMeses = meses.length;

  const thTop: CSSProperties = { position: "sticky", top: ROW1_H, zIndex: 3, background: DARK };
  const grupo: CSSProperties = { position: "sticky", top: 0, zIndex: 4, background: DARK, borderLeft: "2px solid #495057" };
  const frozenTh = (left: number, width: number): CSSProperties => ({ ...thTop, left, minWidth: width, width, zIndex: 5 });
  const frozenTd = (left: number, width: number, bg: string): CSSProperties => ({
    position: "sticky",
    left,
    minWidth: width,
    width,
    zIndex: 2,
    background: bg,
  });

  return (
    <div className="card">
      {/* Feedback de "editable al pasar el cursor" para las celdas del bloque compra */}
      <style>{`
        .celda-editable { cursor: text; transition: background-color .12s ease; }
        .celda-editable:hover { background-color: #eef4ff !important; box-shadow: inset 0 0 0 1px #b6d4fe; }
      `}</style>
      <datalist id={DL_ESTADO}>
        {ESTADOS.map((e) => (
          <option key={e} value={e} />
        ))}
      </datalist>
      <datalist id={DL_REGSIGA}>
        {opcionesRegSiga.map((e) => (
          <option key={e} value={e} />
        ))}
      </datalist>

      <div className="card-body p-0" style={{ maxHeight: "74vh", overflow: "auto" }}>
        <table className="table table-hover text-nowrap mb-0 align-middle" style={{ fontSize: "0.82rem" }}>
          <thead>
            {/* Fila de GRUPOS (como la fila 2 del Excel del doc) */}
            <tr className="table-dark text-uppercase" style={{ fontSize: "0.68rem", letterSpacing: "0.03em" }}>
              <th colSpan={6} style={{ ...grupo, borderLeft: "none" }}>
                Producto
              </th>
              <th colSpan={nMeses} style={grupo}>
                Consumo · 12 meses
              </th>
              <th colSpan={4} style={grupo}>
                Cálculo
              </th>
              <th colSpan={6} style={grupo}>
                Disponibilidad
              </th>
              <th colSpan={12} style={grupo}>
                Estado compra {compraAnio ?? ""} · editable
              </th>
            </tr>
            {/* Fila de COLUMNAS */}
            <tr className="table-dark">
              <th style={frozenTh(0, W_SIGA)}>CÓD. SIGA</th>
              <th style={frozenTh(W_SIGA, W_MED)}>Medicamento</th>
              <th style={thTop}>Cód. med.</th>
              <th style={thTop}>M/I</th>
              <th style={thTop}>_/P</th>
              <th style={thTop}>E/S/_</th>
              {meses.map((m) => (
                <th key={`${m.anio}-${m.mes}`} className="text-end" style={thTop} title={`${m.nombre} ${m.anio}`}>
                  {m.nombre.slice(0, 3)}
                </th>
              ))}
              <th className="text-end" style={thTop} title="Precio unitario (del ICI)">
                Precio
              </th>
              <th className="text-end" style={thTop} title="SUMAMES — consumo de 12 meses">
                Suma 12m
              </th>
              <th className="text-end" style={thTop} title="CONTADOR — meses con consumo">
                Meses c/c
              </th>
              <th className="text-end" style={thTop} title="CPA — consumo promedio mensual">
                CPA
              </th>
              <th className="text-end" style={thTop} title="STOCK — stock de la Red (establecimientos)">
                Stock Red
              </th>
              <th className="text-end" style={thTop} title="Stock_AEM — almacén central">
                Stock AEM
              </th>
              <th className="text-end" style={thTop} title="DISPO = stock_red / CPA">
                Dispo
              </th>
              <th style={thTop}>Situación</th>
              <th className="text-end" style={thTop} title="DISPO_TOTAL = (stock_red + stock_aem) / CPA">
                Dispo total
              </th>
              <th style={thTop}>Sit. total</th>
              {/* Bloque estado compra */}
              <th style={thTop} title="E — Tipo de producto (solo lectura)">
                Tipo producto
              </th>
              {EDITABLES.map((d) => (
                <th key={d.campo} style={thTop} title={d.tecnico}>
                  {d.titulo} <i className="bi bi-pencil-fill" style={{ fontSize: "0.7em", opacity: 0.5 }} aria-hidden="true" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filas.map((fila) => {
              const bg = "#ffffff";
              const c = fila.compra;
              return (
                <tr key={fila.producto_cod}>
                  <td className="text-center" style={{ ...frozenTd(0, W_SIGA, bg), fontSize: "0.74rem", color: "#6c757d" }}>
                    {fila.codigo_siga ?? "—"}
                  </td>
                  <td style={{ ...frozenTd(W_SIGA, W_MED, bg), whiteSpace: "normal" }}>
                    <span className="fw-semibold">{fila.producto_nombre}</span>
                  </td>
                  <td>{fila.producto_cod}</td>
                  <td className="text-center">{fila.medtip ?? "—"}</td>
                  <td className="text-center">{fila.medpet ?? "—"}</td>
                  <td className="text-center">{fila.medest ?? "—"}</td>
                  {fila.meses.map((m) => (
                    <td key={`${m.anio}-${m.mes}`} className="text-end" style={m.consumo === 0 ? { color: "#ccd1d6" } : undefined}>
                      {numero(m.consumo)}
                    </td>
                  ))}
                  <td className="text-end">{fila.precio ? numero(fila.precio, 2) : "—"}</td>
                  <td className="text-end">{numero(fila.sumames)}</td>
                  <td className="text-end">{fila.contador}</td>
                  <td className="text-end fw-semibold">{numero(fila.cpma, 2)}</td>
                  <td className="text-end">{numero(fila.stock_red)}</td>
                  <td className="text-end">{numero(fila.stock_aem)}</td>
                  <td className="text-end">{numero(fila.dispo, 2)}</td>
                  <td>
                    <SituacionBadge situacion={fila.situacion} />
                  </td>
                  <td className="text-end">{numero(fila.dispo_total, 2)}</td>
                  <td>
                    <SituacionBadge situacion={fila.situacion_total} />
                  </td>
                  {/* Bloque estado compra: TIPO PRODUCTO (solo lectura) + 11 editables */}
                  <td style={{ whiteSpace: "normal", maxWidth: 160, background: c.sin_registro ? "#f8f9fa" : undefined }}>
                    {c.tipo_producto ?? "—"}
                  </td>
                  {EDITABLES.map((d, idx) => (
                    <CeldaEditable
                      key={d.campo}
                      def={d}
                      valor={c[d.campo]}
                      editado={c.editados.includes(d.campo)}
                      placeholder={d.campo === "estado_situacion" && c.sin_registro ? "Sin compra centralizada" : undefined}
                      activo={edit?.cod === fila.producto_cod && edit?.idx === idx}
                      navRef={navRef}
                      onActivar={() => activar(fila.producto_cod, idx)}
                      onCerrar={cerrar}
                      onMover={(delta) => moverDesde(fila.producto_cod, idx, delta)}
                      onGuardar={(valor) => onEditar(fila, d.campo, valor)}
                    />
                  ))}
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
            No hay datos para este periodo. Sube el ICI y el archivo de CENARES, luego vuelve aquí.
          </div>
        )}
      </div>
    </div>
  );
}
