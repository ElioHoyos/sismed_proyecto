import { useEffect, useState } from "react";
import { obtenerDisponibilidadRed } from "../services/api";
import type { DisponibilidadRed } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  periodo: string | null;
  filas: DisponibilidadRed[];
}

export function useDisponibilidadRed(periodo: string | undefined): Estado {
  const [estado, setEstado] = useState<Estado>({
    cargando: true,
    error: null,
    periodo: null,
    filas: [],
  });

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerDisponibilidadRed({ periodo })
      .then((respuesta) => {
        if (!vigente) return;
        setEstado({
          cargando: false,
          error: null,
          periodo: respuesta.periodo,
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
