import { useEffect, useRef, useState } from "react";
import { preguntarAsistente } from "../../services/api";
import { useNavegacion, type Pagina } from "../../navegacion";
import type { AsistenteRespuesta } from "../../services/types";

interface Mensaje {
  rol: "user" | "bot";
  texto: string;
  respuesta?: AsistenteRespuesta;
}

const RAPIDAS = ["Próximos a vencer", "Stock negativo", "Desabastecidos", "Quién falta cargar"];

const NOMBRE_PAGINA: Record<string, string> = {
  disponibilidad: "Disponibilidad",
  stock: "Stock",
  vencimientos: "Vencimientos",
  carga: "Carga",
};

const SALUDO: Mensaje = {
  rol: "bot",
  texto:
    "Hola 👋 Soy el asistente. Pregúntame por vencimientos, stock, desabastecidos, CPMA o qué falta cargar. Toca una opción o escribe tu pregunta.",
};

function nuevaSesion(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `s-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }
}

export function AsistenteChat() {
  const { navegar } = useNavegacion();
  const [abierto, setAbierto] = useState(false);
  const [mensajes, setMensajes] = useState<Mensaje[]>([SALUDO]);
  const [input, setInput] = useState("");
  const [enviando, setEnviando] = useState(false);
  const finRef = useRef<HTMLDivElement>(null);
  // Identifica la conversación para ligar reformulaciones (aprendizaje del backend).
  const sesionId = useRef<string>(nuevaSesion());

  useEffect(() => {
    finRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [mensajes, abierto]);

  async function enviar(texto: string) {
    const t = texto.trim();
    if (!t || enviando) return;
    setInput("");
    setMensajes((m) => [...m, { rol: "user", texto: t }]);
    setEnviando(true);
    try {
      const r = await preguntarAsistente(t, sesionId.current);
      setMensajes((m) => [...m, { rol: "bot", texto: r.respuesta_texto, respuesta: r }]);
    } catch {
      setMensajes((m) => [
        ...m,
        { rol: "bot", texto: "No pude consultar el asistente. ¿El servidor (backend) está encendido?" },
      ]);
    } finally {
      setEnviando(false);
    }
  }

  function irAlModulo(r: AsistenteRespuesta) {
    if (!r.enlace) return;
    navegar(r.enlace.pagina as Pagina, r.enlace.filtros);
    setAbierto(false);
  }

  return (
    <>
      {/* Botón flotante */}
      <button
        type="button"
        className="btn btn-primary rounded-circle shadow"
        onClick={() => setAbierto((v) => !v)}
        aria-label={abierto ? "Cerrar asistente" : "Abrir asistente"}
        style={{ position: "fixed", right: 20, bottom: 20, width: 56, height: 56, zIndex: 1060, fontSize: "1.4rem" }}
      >
        <i className={`bi ${abierto ? "bi-x-lg" : "bi-chat-dots-fill"}`} aria-hidden="true" />
      </button>

      {abierto && (
        <div
          className="card shadow-lg"
          role="dialog"
          aria-label="Asistente de consultas"
          style={{
            position: "fixed",
            right: 20,
            bottom: 88,
            width: "min(400px, calc(100vw - 40px))",
            height: "min(600px, calc(100vh - 120px))",
            zIndex: 1060,
            display: "flex",
            flexDirection: "column",
          }}
        >
          <div className="card-header d-flex align-items-center gap-2 bg-primary text-white">
            <i className="bi bi-robot" aria-hidden="true" />
            <strong className="flex-grow-1">Asistente</strong>
            <button
              type="button"
              className="btn btn-sm btn-outline-light border-0"
              onClick={() => setAbierto(false)}
              aria-label="Cerrar"
            >
              <i className="bi bi-x-lg" aria-hidden="true" />
            </button>
          </div>

          <div className="card-body overflow-auto flex-grow-1 bg-body-tertiary" style={{ minHeight: 0 }}>
            {mensajes.map((m, i) => (
              <Burbuja key={i} mensaje={m} onSugerencia={enviar} onVerModulo={irAlModulo} />
            ))}
            {enviando && (
              <div className="text-body-secondary small">
                <span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true" />
                Consultando…
              </div>
            )}
            <div ref={finRef} />
          </div>

          <div className="card-footer">
            <div className="d-flex flex-wrap gap-1 mb-2">
              {RAPIDAS.map((r) => (
                <button
                  key={r}
                  type="button"
                  className="btn btn-sm btn-outline-primary"
                  onClick={() => enviar(r)}
                  disabled={enviando}
                >
                  {r}
                </button>
              ))}
            </div>
            <form
              className="input-group"
              onSubmit={(e) => {
                e.preventDefault();
                enviar(input);
              }}
            >
              <input
                type="text"
                className="form-control"
                placeholder="Escribe tu pregunta…"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                disabled={enviando}
                aria-label="Pregunta"
              />
              <button type="submit" className="btn btn-primary" disabled={enviando || !input.trim()}>
                <i className="bi bi-send-fill" aria-hidden="true" />
              </button>
            </form>
          </div>
        </div>
      )}
    </>
  );
}

function Burbuja({
  mensaje,
  onSugerencia,
  onVerModulo,
}: {
  mensaje: Mensaje;
  onSugerencia: (texto: string) => void;
  onVerModulo: (r: AsistenteRespuesta) => void;
}) {
  const esUsuario = mensaje.rol === "user";
  const r = mensaje.respuesta;
  const datos = r?.datos;
  const mostrarSugerencias =
    r && (r.intencion_detectada === "desconocida" || !r.enlace) && (r.sugerencias?.length ?? 0) > 0;

  return (
    <div className={`d-flex mb-2 ${esUsuario ? "justify-content-end" : "justify-content-start"}`}>
      <div
        className={`p-2 rounded-3 ${esUsuario ? "bg-primary text-white" : "bg-body border"}`}
        style={{ maxWidth: "90%" }}
      >
        <div className="small" style={{ whiteSpace: "pre-wrap" }}>
          {mensaje.texto}
        </div>

        {datos && datos.total > 0 && (
          <div className="mt-2" style={{ maxHeight: 220, overflow: "auto" }}>
            <table className="table table-sm table-striped mb-1" style={{ fontSize: "0.75rem" }}>
              <thead>
                <tr>
                  {datos.columnas.map((c) => (
                    <th key={c} className="text-nowrap">
                      {c}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {datos.filas.map((fila, i) => (
                  <tr key={i}>
                    {fila.map((celda, j) => (
                      <td key={j} className="text-nowrap">
                        {celda}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {datos.total > datos.filas.length && (
              <div className="text-body-secondary" style={{ fontSize: "0.7rem" }}>
                Mostrando {datos.filas.length} de {datos.total}.
              </div>
            )}
          </div>
        )}

        {r?.enlace && (
          <button
            type="button"
            className="btn btn-sm btn-outline-primary mt-2"
            onClick={() => onVerModulo(r)}
          >
            <i className="bi bi-box-arrow-up-right me-1" aria-hidden="true" />
            Ver en {NOMBRE_PAGINA[r.enlace.pagina] ?? r.enlace.pagina}
          </button>
        )}

        {mostrarSugerencias && (
          <div className="d-flex flex-wrap gap-1 mt-2">
            {r!.sugerencias.map((s) => (
              <button
                key={s}
                type="button"
                className="btn btn-sm btn-light border"
                style={{ fontSize: "0.72rem" }}
                onClick={() => onSugerencia(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
