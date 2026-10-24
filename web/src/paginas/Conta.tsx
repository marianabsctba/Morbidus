import { FormEvent, useEffect, useState } from "react";
import { api, ApiKey, Conta as ContaT } from "../api";
import { FINALIDADES } from "../dados";
import { dataHoraBr } from "../util";

type Props = { conta: ContaT; atualizar: () => void; tratarErro: (e: unknown) => string };

export default function Conta({ conta, atualizar, tratarErro }: Props) {
  const [chaves, setChaves] = useState<ApiKey[]>([]);
  const [nome, setNome] = useState("");
  const [nova, setNova] = useState<string | null>(null);
  const [copiado, setCopiado] = useState(false);
  const [erro, setErro] = useState<string | null>(null);

  const carregar = () =>
    api
      .chaves()
      .then(setChaves)
      .catch((e) => setErro(tratarErro(e)));

  useEffect(() => {
    carregar();
    atualizar();
  }, []);

  async function gerar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      const k = await api.gerarChave(nome.trim());
      setNova(k.chave);
      setCopiado(false);
      setNome("");
      carregar();
    } catch (err) {
      setErro(tratarErro(err));
    }
  }

  async function revogar(id: string) {
    if (!window.confirm("Revogar esta chave? Integrações que a usam vão parar de funcionar.")) return;
    try {
      await api.revogarChave(id);
      carregar();
    } catch (err) {
      setErro(tratarErro(err));
    }
  }

  const ilimitado = conta.limite_diario === 0;
  const pct = ilimitado ? 0 : Math.min(100, (conta.consultas_hoje / conta.limite_diario) * 100);

  return (
    <>
      <div className="titulo-pagina">
        <h1>Minha conta</h1>
        <p>{conta.email}</p>
      </div>
      {erro && (
        <div className="alerta" style={{ marginBottom: 20 }}>
          {erro}
        </div>
      )}

      <div className="conta-grade">
        <div className="painel">
          <h2>Cadastro</h2>
          <dl className="ficha">
            <dt>Nome</dt>
            <dd>{conta.nome}</dd>
            <dt>Organização</dt>
            <dd>{conta.organizacao ?? "não informada"}</dd>
            <dt>Uso declarado</dt>
            <dd>{FINALIDADES[conta.uso_pretendido as keyof typeof FINALIDADES] ?? "Pesquisa"}</dd>
            <dt>Desde</dt>
            <dd>{dataHoraBr(conta.criado_em)}</dd>
          </dl>
        </div>

        <div className="painel">
          <h2>Consultas hoje</h2>
          <div className="kpi" style={{ padding: 0 }}>
            <div className="valor vivo">
              {conta.consultas_hoje}
              <span className="mudo" style={{ fontSize: 18 }}>
                {ilimitado ? " / sem limite" : ` / ${conta.limite_diario}`}
              </span>
            </div>
          </div>
          {!ilimitado && (
            <div className="medidor-linha" aria-hidden="true">
              <span style={{ width: `${pct}%` }} />
            </div>
          )}
          <p className="mudo" style={{ fontSize: 13, marginBottom: 0 }}>
            O limite vale para o painel e para as suas API keys somados, e renova à meia-noite (UTC).
          </p>
        </div>
      </div>

      <div className="painel" style={{ marginTop: 28 }}>
        <h2>API keys</h2>
        <p className="mudo" style={{ marginTop: -6 }}>
          Só se você quiser integrar o MORBiDus a outro sistema. Para usar o painel, não precisa.
        </p>

        {nova && (
          <div className="chave-nova" role="status">
            <p>Copie agora: esta chave não será mostrada de novo.</p>
            <code>{nova}</code>
            <div style={{ display: "flex", gap: 10, marginTop: 10 }}>
              <button
                className="botao fantasma"
                onClick={() => {
                  navigator.clipboard?.writeText(nova);
                  setCopiado(true);
                }}
              >
                {copiado ? "Copiada" : "Copiar"}
              </button>
              <button className="botao fantasma" onClick={() => setNova(null)}>
                Já guardei
              </button>
            </div>
          </div>
        )}

        <form className="gerar-chave" onSubmit={gerar}>
          <div className="campo" style={{ marginBottom: 0, flex: 1 }}>
            <label htmlFor="k-nome">Nome da chave</label>
            <input
              id="k-nome"
              placeholder="ex.: sistema de onboarding"
              value={nome}
              onChange={(e) => setNome(e.target.value)}
            />
          </div>
          <button className="botao" disabled={nome.trim().length < 2}>
            Gerar chave
          </button>
        </form>

        {chaves.length > 0 && (
          <div className="tabela-wrap" style={{ marginTop: 20 }}>
            <table className="tabela">
              <thead>
                <tr>
                  <th>Nome</th>
                  <th>Prefixo</th>
                  <th>Criada</th>
                  <th>Situação</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {chaves.map((k) => (
                  <tr key={k.id}>
                    <td>{k.nome}</td>
                    <td className="dado">mbd_{k.prefixo}_…</td>
                    <td className="dado">{dataHoraBr(k.criado_em)}</td>
                    <td>
                      {k.revogada_em ? (
                        <span className="etiqueta">revogada</span>
                      ) : (
                        <span className="etiqueta osso">
                          <span className="ponto" />
                          ativa
                        </span>
                      )}
                    </td>
                    <td className="num">
                      {!k.revogada_em && (
                        <button className="botao fantasma" onClick={() => revogar(k.id)}>
                          Revogar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </>
  );
}
