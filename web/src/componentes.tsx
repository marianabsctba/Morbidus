import type { Status } from "./api";
import { STATUS } from "./dados";

export function Atmosfera() {
  return (
    <div className="atmosfera" aria-hidden="true">
      <div className="alarme" />
      <div className="grao" />
      <div className="scan" />
      <div className="vinheta" />
      <div className="queda" />
    </div>
  );
}

export function Marca({ className = "" }: { className?: string }) {
  return (
    <span className={`marca ${className}`} aria-label="MORBiDus">
      MOR<span className="falha">B</span>
      <span className="id">iD</span>us
    </span>
  );
}

export function EtiquetaStatus({ status }: { status: Status }) {
  const s = STATUS[status];
  return (
    <span className={`etiqueta ${s.tom}`}>
      <span className="ponto" />
      {s.rotulo}
    </span>
  );
}

export function Medidor({ valor }: { valor: number }) {
  const raio = 56;
  const circ = 2 * Math.PI * raio;
  const pct = Math.round(valor * 100);
  const cor = valor >= 0.85 ? "var(--sangue)" : valor >= 0.6 ? "var(--brasa)" : "var(--cinza)";
  return (
    <div className="medidor" role="img" aria-label={`Score ${pct} de 100`}>
      <svg width="132" height="132" viewBox="0 0 132 132">
        <circle cx="66" cy="66" r={raio} fill="none" stroke="var(--borda)" strokeWidth="8" />
        <circle
          cx="66"
          cy="66"
          r={raio}
          fill="none"
          stroke={cor}
          strokeWidth="8"
          strokeLinecap="round"
          strokeDasharray={circ}
          strokeDashoffset={circ * (1 - valor)}
          style={{ filter: `drop-shadow(0 0 6px ${cor})`, transition: "stroke-dashoffset 0.8s ease-out" }}
        />
      </svg>
      <div className="valor">
        <div>
          {pct}
          <small>SCORE</small>
        </div>
      </div>
    </div>
  );
}
