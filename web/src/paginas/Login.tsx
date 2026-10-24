import { FormEvent, useState } from "react";
import { api } from "../api";
import { Marca } from "../componentes";

export default function Login({ aoEntrar }: { aoEntrar: (chave: string) => void }) {
  const [chave, setChave] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function entrar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      await api.validarChave(chave.trim());
      aoEntrar(chave.trim());
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Falha ao validar a chave");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="login">
      <div className="cartaz">
        <h1 style={{ margin: 0 }}>
          <Marca />
        </h1>
        <p className="tagline">
          Dead identities. <em>Living fraud.</em>
        </p>
        <p className="difp">Death Identity Fraud Prevention</p>
        <div className="gotas" />

        <form className="painel" onSubmit={entrar}>
          <h2>Acesso restrito</h2>
          <div className="campo">
            <label htmlFor="chave">API key</label>
            <input
              id="chave"
              type="password"
              autoComplete="current-password"
              placeholder="mbd_xxxxxxxx_..."
              value={chave}
              onChange={(e) => setChave(e.target.value)}
              required
            />
            <span className="dica">A chave fica só nesta aba e some quando você a fecha.</span>
          </div>
          {erro && (
            <div className="alerta" role="alert" style={{ marginBottom: 16 }}>
              {erro}
            </div>
          )}
          <button className="botao largo" disabled={carregando || !chave.trim()}>
            {carregando ? "Verificando..." : "Entrar"}
          </button>
        </form>
        <p className="rodape-login">
          Plataforma aberta para identificar o uso de identidades de pessoas falecidas.
        </p>
      </div>
    </main>
  );
}
