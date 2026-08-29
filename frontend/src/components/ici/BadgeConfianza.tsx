import type { ConfianzaDeteccion } from "../../services/types";

const META: Record<
  ConfianzaDeteccion,
  { label: string; clase: string; icono: string; titulo: string }
> = {
  alta: {
    label: "Detectado",
    clase: "text-bg-success",
    icono: "bi-check-circle-fill",
    titulo: "Establecimiento detectado con alta confianza",
  },
  dudosa: {
    label: "Confirmar",
    clase: "text-bg-warning",
    icono: "bi-exclamation-triangle-fill",
    titulo: "Detección dudosa: revisa y confirma el establecimiento",
  },
  no_encontrado: {
    label: "Sin detectar",
    clase: "text-bg-danger",
    icono: "bi-x-circle-fill",
    titulo: "No se pudo detectar: asigna el establecimiento manualmente",
  },
};

export function BadgeConfianza({ confianza }: { confianza: ConfianzaDeteccion }) {
  const meta = META[confianza];
  return (
    <span
      className={`badge ${meta.clase} d-inline-flex align-items-center gap-1`}
      title={meta.titulo}
    >
      <i className={`bi ${meta.icono}`} aria-hidden="true" />
      {meta.label}
    </span>
  );
}
