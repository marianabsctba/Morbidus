import { useCallback, useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { getKey, NaoAutorizado, setKey } from "./api";
import { Atmosfera, Marca } from "./componentes";
import Auditoria from "./paginas/Auditoria";
import Cobertura from "./paginas/Cobertura";
import Consulta from "./paginas/Consulta";
import Login from "./paginas/Login";

const FX = "morbidus.fx";

function lerFx(): boolean {
  try {
    return localStorage.getItem(FX) !== "off";
  } catch {
    return true;
  }
}

export default function App() {
  const [chave, setChave] = useState<string | null>(getKey());
  const [fx, setFx] = useState(lerFx);

  useEffect(() => {
    document.documentElement.dataset.fx = fx ? "on" : "off";
    try {
      localStorage.setItem(FX, fx ? "on" : "off");
    } catch {
      // Sem storage, a preferência vale só nesta visita.
    }
  }, [fx]);

  const sair = useCallback(() => {
    setKey(null);
    setChave(null);
  }, []);

  // Qualquer página que receba 401/403 derruba a sessão.
  const tratarErro = useCallback(
    (e: unknown): string => {
      if (e instanceof NaoAutorizado) {
        sair();
        return e.message;
      }
      return e instanceof Error ? e.message : String(e);
    },
    [sair],
  );

  if (!chave) {
    return (
      <>
        <Atmosfera />
        <Login
          aoEntrar={(k) => {
            setKey(k);
            setChave(k);
          }}
        />
      </>
    );
  }

  return (
    <>
      <Atmosfera />
      <div className="app">
        <header className="topo">
          <Marca />
          <nav aria-label="Principal">
            <NavLink to="/consulta" className={({ isActive }) => (isActive ? "ativo" : "")}>
              Consulta
            </NavLink>
            <NavLink to="/auditoria" className={({ isActive }) => (isActive ? "ativo" : "")}>
              Auditoria
            </NavLink>
            <NavLink to="/cobertura" className={({ isActive }) => (isActive ? "ativo" : "")}>
              Cobertura
            </NavLink>
          </nav>
          <div className="direita">
            <button
              className="botao fantasma"
              aria-pressed={fx}
              onClick={() => setFx(!fx)}
              title="Liga ou desliga as luzes piscando e os efeitos de fundo"
            >
              {fx ? "Luzes: ligadas" : "Luzes: desligadas"}
            </button>
            <button className="botao fantasma" onClick={sair}>
              Sair
            </button>
          </div>
        </header>
        <main className="conteudo">
          <Routes>
            <Route path="/consulta" element={<Consulta tratarErro={tratarErro} />} />
            <Route path="/auditoria" element={<Auditoria tratarErro={tratarErro} />} />
            <Route path="/cobertura" element={<Cobertura tratarErro={tratarErro} />} />
            <Route path="*" element={<Navigate to="/consulta" replace />} />
          </Routes>
        </main>
        <footer className="rodape">
          <span>MORBiDus · Death Identity Fraud Prevention · open source e gratuito</span>
          <span>Toda consulta é registrada com finalidade declarada (LGPD).</span>
        </footer>
      </div>
    </>
  );
}
