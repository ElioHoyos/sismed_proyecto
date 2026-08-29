import { useEffect, useState } from "react";
import { obtenerEstablecimientos } from "../services/api";
import type { EstablecimientoOut } from "../services/types";

interface Estado {
  cargando: boolean;
  error: string | null;
  establecimientos: EstablecimientoOut[];
}

/** Catálogo de establecimientos activos, para poblar los <select> de
 * corrección en la carga de ICI. */
export function useEstablecimientos(): Estado {
  const [estado, setEstado] = useState<Estado>({
    cargando: true,
    error: null,
    establecimientos: [],
  });

  useEffect(() => {
    let vigente = true;

    obtenerEstablecimientos()
      .then((establecimientos) => {
        if (vigente) setEstado({ cargando: false, error: null, establecimientos });
      })
      .catch((error: unknown) => {
        if (vigente)
          setEstado({
            cargando: false,
            error: error instanceof Error ? error.message : "Error desconocido",
            establecimientos: [],
          });
      });

    return () => {
      vigente = false;
    };
  }, []);

  return estado;
}
