import { useEffect, useState } from "react";
import { obtenerResumenSituacionRed } from "../services/api";
import type { SituacionResumenItem } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  periodo: string | null;
  // Dos indicadores independientes por MEDEST (Estratégicos excluidos):
  totalSoporte: number;
  totalSis: number;
  soporte: SituacionResumenItem[];
  sis: SituacionResumenItem[];
}

/** Siempre desde /api/disponibilidad/red/resumen — el % de situación de la red
 * nunca sale de contar filas de la vista por establecimiento. Dividido en dos
 * indicadores: Soporte (S) y SIS (_). */
export function useResumenSituacionRed(periodo: string | undefined): Estado {
  const [estado, setEstado] = useState<Estado>({
    cargando: true,
    error: null,
    periodo: null,
    totalSoporte: 0,
    totalSis: 0,
    soporte: [],
    sis: [],
  });

  useEffect(() => {
    let vigente = true;
    setEstado((prev) => ({ ...prev, cargando: true, error: null }));

    obtenerResumenSituacionRed({ periodo })
      .then((r) => {
        if (!vigente) return;
        setEstado({
          cargando: false,
          error: null,
          periodo: r.periodo,
          totalSoporte: r.total_soporte,
          totalSis: r.total_sis,
          soporte: r.soporte,
          sis: r.sis,
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
