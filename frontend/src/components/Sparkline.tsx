interface Props {
  valores: number[];
  ancho?: number;
  alto?: number;
  color?: string;
}

/** Micro-gráfico de barras (sparkline) para ver la tendencia de la serie de
 * consumo de un vistazo. Sin dependencias — SVG puro. */
export function Sparkline({ valores, ancho = 72, alto = 22, color = "#0d6efd" }: Props) {
  if (!valores.length) return null;
  const max = Math.max(...valores, 1);
  const n = valores.length;
  const gap = 1;
  const bw = (ancho - gap * (n - 1)) / n;

  return (
    <svg width={ancho} height={alto} role="img" aria-label="Tendencia de consumo" style={{ display: "block" }}>
      {valores.map((v, i) => {
        const h = v <= 0 ? 1 : Math.max(1, (v / max) * alto);
        return (
          <rect
            key={i}
            x={i * (bw + gap)}
            y={alto - h}
            width={bw}
            height={h}
            rx={0.5}
            fill={v <= 0 ? "#dee2e6" : color}
          />
        );
      })}
    </svg>
  );
}
