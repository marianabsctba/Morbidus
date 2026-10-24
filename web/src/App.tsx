import { useCallback, useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, Conta as ContaT, NaoAutorizado } from "./api";
import { Atmosfera, Marca } from "./componentes";
import Admin from "./paginas/Admin";
import Auditoria from "./paginas/Auditoria";
import Cobertura from "./paginas/Cobertura";
import Consulta from "./paginas/Consulta";
import Conta from "./paginas/Conta";
import Entrada from "./paginas/Entrada";
import Verificar from "./paginas/Verificar";

function AdminSemMfa() {
  return (
    <div className="painel" style={{ maxWidth: 560 }}>
      <h2>Administração bloqueada</h2>
      <p>
        Para proteger os dados de todas as contas, a área de Administração só abre com a verificação em duas
        etapas (MFA) ativa.
      </p>
      <NavLink to="/conta" className="botao">
        Ativar MFA em Minha conta
      </NavLink>
    </div>
  );
}

const FX = "morbidus.fx";

function lerFx(): boolean {
  try {
    return localStorage.getItem(FX) !== "off";
  } catch {
    return true;
  }
}

export default function App() {
  const [conta, setConta] = useState<ContaT | null | undefined>(undefined);
  const [fx, setFx] = useState(lerFx);
  const local = useLocation();
  const navegar = useNavigate();

  useEffect(() => {
    document.documentElement.dataset.fx = fx ? "on" : "off";
    try {
      localStorage.setItem(FX, fx ? "on" : "off");
    } catch {
      // Sem storage, a preferência vale só nesta visita.
    }
  }, [fx]);

  const atualizarConta = useCallback(() => {
    api
      .conta()
      .then(setConta)
      .catch(() => setConta(null));
  }, []);

  useEffect(atualizarConta, [atualizarConta]);

  const sair = useCallback(() => {
    api.sair().catch(() => undefined);
    setConta(null);
  }, []);

  // 401 em qualquer página derruba a sessão; o resto vira mensagem.
  const tratarErro = useCallback((e: unknown): string => {
    if (e instanceof NaoAutorizado) {
      setConta(null);
      return e.message;
    }
    return e instanceof Error ? e.message : String(e);
  }, []);

  if (local.pathname === "/verificar") {
    return (
      <>
        <Atmosfera />
        <Verificar aoConcluir={() => navegar("/", { replace: true })} />
      </>
    );
  }

  if (conta === undefined) {
    return (
      <>
        <Atmosfera />
        <main className="login">
          <p className="carregando">ABRINDO A CRIPTA</p>
        </main>
      </>
    );
  }

  if (conta === null) {
    return (
      <>
        <Atmosfera />
        <Entrada aoEntrar={atualizarConta} />
      </>
    );
  }

  const ativo = ({ isActive }: { isActive: boolean }) => (isActive ? "ativo" : "");

  return (
    <>
      <Atmosfera />
      <div className="app">
        <header className="topo">
          <Marca />
          <nav aria-label="Principal">
            <NavLink to="/consulta" className={ativo}>
              Consulta
            </NavLink>
            <NavLink to="/auditoria" className={ativo}>
              Auditoria
            </NavLink>
            <NavLink to="/cobertura" className={ativo}>
              Cobertura
            </NavLink>
            <NavLink to="/conta" className={ativo}>
              Minha conta
            </NavLink>
            {conta.admin && (
              <NavLink to="/admin" className={ativo}>
                Administração
              </NavLink>
            )}
          </nav>
          <div className="direita">
            <span className="uso-topo" title="Consultas feitas hoje">
              {conta.consultas_hoje}
              {conta.limite_diario > 0 ? `/${conta.limite_diario}` : ""} hoje
            </span>
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
            <Route
              path="/consulta"
              element={<Consulta tratarErro={tratarErro} aoConsultar={atualizarConta} />}
            />
            <Route path="/auditoria" element={<Auditoria tratarErro={tratarErro} />} />
            <Route path="/cobertura" element={<Cobertura tratarErro={tratarErro} admin={conta.admin} />} />
            {conta.admin && (
              <Route
                path="/admin"
                element={conta.mfa_ativo ? <Admin tratarErro={tratarErro} /> : <AdminSemMfa />}
              />
            )}
            <Route
              path="/conta"
              element={<Conta conta={conta} atualizar={atualizarConta} tratarErro={tratarErro} />}
            />
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
