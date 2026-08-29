import { useEffect, useState } from "react";
import { obtenerDisponibilidad } from "../services/api";
import type { DisponibilidadEstablecimiento } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  periodo: string | null;
  nota: string | null;
  filas: DisponibilidadEstablecimiento[];
}

export function useDisponibilidadEstablecimiento(periodo: string | undefined): Estado {
  const [estado, setEstado] = useState<Estado>({
    cargando: true,
    error: null,
    periodo: null,
    nota: null,
    filas: [],
  });

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerDisponibilidad({ periodo })
      .then((respuesta) => {
        if (!vigente) return;
        setEstado({
          cargando: false,
          error: null,
          periodo: respuesta.periodo,
          nota: respuesta.nota,
          filas: respuesta.resultados,
        });
      })
      .catch((error: unknown) => {
        if (!vigente) return;
        setEstado((prev) => ({
          ...prev,
          cargando: false,
          error: error instanceof Error ? error.message : "Error desconocido",
        }));
      });

    return () => {
      vigente = false;
    };
  }, [periodo]);

  return estado;
}
