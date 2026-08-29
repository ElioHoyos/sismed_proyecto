import type { Situacion } from "./types";

export interface SituacionMeta {
  /** Etiqueta amigable (Title Case) que ve el usuario. */
  label: string;
  /** Color de fondo del badge / segmento de barra. */
  color: string;
  /** true si el texto sobre `color` debe ser oscuro (fondos claros). */
  textoOscuro: boolean;
  /** Icono de bootstrap-icons. */
  icono: string;
  /** Explicación con el umbral real (ver backend `clasificar_situacion`). */
  descripcion: string;
}

/**
 * Orden por urgencia de acción: lo más crítico primero. Se usa para ordenar
 * los chips del resumen, la barra apilada, la leyenda y el desplegable de
 * filtro — así el usuario ve primero lo que debe atender.
 */
export const SITUACION_ORDEN: Situacion[] = [
  "DESABASTECIDO",
  "CRITICO",
  "SUBSTOCK",
  "NORMOSTOCK",
  "SOBRESTOCK",
  "SIN ROTACION",
];

/**
 * Fuente única de verdad de cómo se presenta cada situación. Los umbrales de
 * las descripciones calzan con `clasificar_situacion` del backend
 * (dispo = meses de stock = stock ÷ consumo mensual):
 *   cpma == 0            → SIN ROTACION
 *   dispo == 0           → DESABASTECIDO
 *   dispo < 1            → CRITICO
 *   1 ≤ dispo ≤ 2        → SUBSTOCK
 *   2 < dispo ≤ 6        → NORMOSTOCK
 *   dispo > 6            → SOBRESTOCK
 */
export const SITUACION_META: Record<Situacion, SituacionMeta> = {
  DESABASTECIDO: {
    label: "Desabastecido",
    color: "#842029",
    textoOscuro: false,
    icono: "bi-x-octagon-fill",
    descripcion: "Sin stock disponible (0 meses de cobertura). Requiere reposición urgente.",
  },
  CRITICO: {
    label: "Crítico",
    color: "#dc3545",
    textoOscuro: false,
    icono: "bi-exclamation-triangle-fill",
    descripcion: "Menos de 1 mes de stock. Se agota muy pronto.",
  },
  SUBSTOCK: {
    label: "Substock",
    color: "#ffc107",
    textoOscuro: true,
    icono: "bi-arrow-down-circle-fill",
    descripcion: "Entre 1 y 2 meses de stock. Por debajo del nivel ideal.",
  },
  NORMOSTOCK: {
    label: "Normostock",
    color: "#198754",
    textoOscuro: false,
    icono: "bi-check-circle-fill",
    descripcion: "Entre 2 y 6 meses de stock. Nivel adecuado.",
  },
  SOBRESTOCK: {
    label: "Sobrestock",
    color: "#0d6efd",
    textoOscuro: false,
    icono: "bi-arrow-up-circle-fill",
    descripcion: "Más de 6 meses de stock. Exceso; riesgo de vencimiento o inmovilizado.",
  },
  "SIN ROTACION": {
    label: "Sin rotación",
    color: "#6c757d",
    textoOscuro: false,
    icono: "bi-dash-circle-fill",
    descripcion: "Sin consumo en los últimos 12 meses. El producto no rota.",
  },
};
