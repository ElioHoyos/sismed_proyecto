/** Opciones y significados de las clasificaciones crudas del catálogo:
 * MEDTIP (Tipo: M/I) y MEDPET (Financiamiento: P/_). La etiqueta explica el
 * código y lo muestra entre paréntesis; el value es el código crudo con el que
 * se filtra en el backend. */
export const OPCIONES_TIPO = [
  { value: "M", label: "Medicamento (M)" },
  { value: "I", label: "Insumo (I)" },
];

export const OPCIONES_FINANCIAMIENTO = [
  { value: "P", label: "Petitorio (P)" },
  { value: "_", label: "SIS (_)" },
];

export const OPCIONES_MEDEST = [
  { value: "S", label: "Soporte (S)" },
  { value: "_", label: "SIS (_)" },
  { value: "E", label: "Estratégico (E)" },
];

export const SIGNIFICADO_MEDTIP: Record<string, string> = { M: "Medicamento", I: "Insumo" };
export const SIGNIFICADO_MEDPET: Record<string, string> = { P: "Petitorio", _: "SIS" };
export const SIGNIFICADO_MEDEST: Record<string, string> = {
  S: "Soporte",
  _: "SIS",
  E: "Estratégico",
};
