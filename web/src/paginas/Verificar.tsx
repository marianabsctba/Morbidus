import { useEffect, useState } from "react";
import { api } from "../api";
import { Marca } from "../componentes";

export default function Verificar({ aoConcluir }: { aoConcluir: () => void }) {
  const [estado, setEstado] = useState<"verificando" | "ok" | "erro">("verificando");
  const [erro, setErro] = useState("");

  useEffect(() => {
    const token = new URLSearchParams(window.location.search).get("token");
    if (!token) {
      setEstado("erro");
      setErro("Link incompleto.");
      return;
    }
    api
      .verificar(token)
      .then(() => setEstado("ok"))
      .catch((e) => {
        setEstado("erro");
        setErro(e instanceof Error ? e.message : String(e));
      });
  }, []);

  return (
    <main className="login">
      <div className="cartaz">
        <h1 style={{ margin: 0 }}>
          <Marca />
        </h1>
        <div className="gotas" style={{ marginTop: 32 }} />
        <div className="painel" style={{ textAlign: "center" }}>
          {estado === "verificando" && <p className="carregando">CONFIRMANDO</p>}
          {estado === "ok" && <p>E-mail confirmado. Sua conta está ativa.</p>}
          {estado === "erro" && <div className="alerta">{erro}</div>}
          {estado !== "verificando" && (
            <button className="botao largo" style={{ marginTop: 18 }} onClick={aoConcluir}>
              Ir para o login
            </button>
          )}
        </div>
      </div>
    </main>
  );
}
