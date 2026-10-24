import { useCallback, useEffect, useMemo, useState } from "react";
import { api, AuditEntryGeral, Fonte, UsuarioAdmin, UsuarioAdminIn } from "../api";
import { EtiquetaStatus } from "../componentes";
import { FINALIDADES } from "../dados";
import { dataHoraBr } from "../util";

type Aba = "usuarios" | "auditoria" | "fontes";
type Props = { tratarErro: (e: unknown) => string };

const LIMITES: [string, number | null][] = [
  ["Padrão (50)", null],
  ["200 por dia", 200],
  ["1.000 por dia", 1000],
  ["Ilimitado", 0],
];

export default function Admin({ tratarErro }: Props) {
  const [aba, setAba] = useState<Aba>("usuarios");
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [erro, setErro] = useState<string | null>(null);

  const carregarUsuarios = useCallback(
    () =>
      api
        .usuarios()
        .then(setUsuarios)
        .catch((e) => setErro(tratarErro(e))),
    [tratarErro],
  );

  useEffect(() => {
    carregarUsuarios();
  }, [carregarUsuarios]);

  const pendentes = usuarios.filter((u) => !u.liberado && u.ativo).length;

  return (
    <>
      <div className="titulo-pagina">
        <h1>Administração</h1>
        <p>Visível só para administradoras.</p>
      </div>
      <div className="abas abas-pagina" role="tablist">
        <button role="tab" aria-selected={aba === "usuarios"} onClick={() => setAba("usuarios")}>
          Usuários{pendentes > 0 && <span className="contador">{pendentes}</span>}
        </button>
        <button role="tab" aria-selected={aba === "auditoria"} onClick={() => setAba("auditoria")}>
          Auditoria geral
        </button>
        <button role="tab" aria-selected={aba === "fontes"} onClick={() => setAba("fontes")}>
          Fontes
        </button>
      </div>
      {erro && (
        <div className="alerta" style={{ marginBottom: 20 }}>
          {erro}
        </div>
      )}
      {aba === "usuarios" && (
        <Usuarios usuarios={usuarios} recarregar={carregarUsuarios} setErro={setErro} tratarErro={tratarErro} />
      )}
      {aba === "auditoria" && <AuditoriaGeral usuarios={usuarios} tratarErro={tratarErro} setErro={setErro} />}
      {aba === "fontes" && <Fontes tratarErro={tratarErro} setErro={setErro} />}
    </>
  );
}

function situacao(u: UsuarioAdmin) {
  if (!u.ativo) return <span className="etiqueta sangue">bloqueado</span>;
  if (!u.liberado) return <span className="etiqueta brasa">pendente</span>;
  return (
    <span className="etiqueta osso">
      <span className="ponto" />
      ativo
    </span>
  );
}

function Usuarios({
  usuarios,
  recarregar,
  setErro,
  tratarErro,
}: {
  usuarios: UsuarioAdmin[];
  recarregar: () => void;
  setErro: (e: string | null) => void;
  tratarErro: (e: unknown) => string;
}) {
  const [soPendentes, setSoPendentes] = useState(false);
  const lista = useMemo(() => {
    const ordenada = [...usuarios].sort((a, b) => Number(a.liberado) - Number(b.liberado));
    return soPendentes ? ordenada.filter((u) => !u.liberado && u.ativo) : ordenada;
  }, [usuarios, soPendentes]);

  async function alterar(u: UsuarioAdmin, body: UsuarioAdminIn, confirmar?: string) {
    if (confirmar && !window.confirm(confirmar)) return;
    setErro(null);
    try {
      await api.alterarUsuario(u.id, body);
      recarregar();
    } catch (e) {
      setErro(tratarErro(e));
    }
  }

  return (
    <div className="painel">
      <h2>Contas</h2>
      <label className="aceite" style={{ marginTop: -6 }}>
        <input type="checkbox" checked={soPendentes} onChange={(e) => setSoPendentes(e.target.checked)} />
        <span>Mostrar só contas aguardando aprovação</span>
      </label>
      {lista.length === 0 ? (
        <p className="mudo">Nenhuma conta aqui.</p>
      ) : (
        <div className="tabela-wrap">
          <table className="tabela">
            <thead>
              <tr>
                <th>Conta</th>
                <th>Uso declarado</th>
                <th>Criada</th>
                <th>Situação</th>
                <th>Hoje</th>
                <th>Limite</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lista.map((u) => (
                <tr key={u.id}>
                  <td>
                    <div>
                      {u.nome} {u.admin && <span className="etiqueta sangue">admin</span>}
                    </div>
                    <div className="dado mudo" style={{ fontSize: 12 }}>
                      {u.email}
                      {u.organizacao ? ` · ${u.organizacao}` : ""}
                    </div>
                  </td>
                  <td>{FINALIDADES[u.uso_pretendido as keyof typeof FINALIDADES] ?? "Pesquisa"}</td>
                  <td className="dado">{dataHoraBr(u.criado_em)}</td>
                  <td>{situacao(u)}</td>
                  <td className="num">{u.consultas_hoje}</td>
                  <td>
                    <select
                      className="mini"
                      value={u.limite_diario === 0 ? "0" : LIMITES.some(([, v]) => v === u.limite_diario) ? String(u.limite_diario) : ""}
                      onChange={(e) => alterar(u, { limite_diario: e.target.value === "" ? null : Number(e.target.value) })}
                      aria-label={`Limite diário de ${u.email}`}
                    >
                      {LIMITES.map(([rotulo, valor]) => (
                        <option key={rotulo} value={valor === null ? "" : String(valor)}>
                          {rotulo}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td className="acoes">
                    {!u.liberado && u.ativo && (
                      <button className="botao fantasma" onClick={() => alterar(u, { liberado: true })}>
                        Aprovar
                      </button>
                    )}
                    {u.ativo ? (
                      <button
                        className="botao fantasma"
                        onClick={() => alterar(u, { ativo: false }, `Bloquear ${u.email}? A sessão dela cai na hora.`)}
                      >
                        Bloquear
                      </button>
                    ) : (
                      <button className="botao fantasma" onClick={() => alterar(u, { ativo: true })}>
                        Reativar
                      </button>
                    )}
                    {u.liberado && u.ativo && (
                      <button
                        className="botao fantasma"
                        onClick={() =>
                          alterar(
                            u,
                            { admin: !u.admin },
                            u.admin ? `Tirar o acesso de administração de ${u.email}?` : `Tornar ${u.email} administradora?`,
                          )
                        }
                      >
                        {u.admin ? "Tirar admin" : "Tornar admin"}
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
  );
}

const PAGINA = 50;

function AuditoriaGeral({
  usuarios,
  tratarErro,
  setErro,
}: {
  usuarios: UsuarioAdmin[];
  tratarErro: (e: unknown) => string;
  setErro: (e: string | null) => void;
}) {
  const [itens, setItens] = useState<AuditEntryGeral[]>([]);
  const [conta, setConta] = useState("");
  const [ip, setIp] = useState("");
  const [fim, setFim] = useState(false);
  const [carregando, setCarregando] = useState(false);
  const porTenant = useMemo(() => Object.fromEntries(usuarios.map((u) => [u.tenant_id, u])), [usuarios]);

  const carregar = useCallback(
    async (offset: number) => {
      setCarregando(true);
      try {
        const novos = await api.auditoriaGeral(offset, PAGINA, { tenantId: conta || undefined, ip: ip || undefined });
        setItens((atual) => (offset === 0 ? novos : [...atual, ...novos]));
        setFim(novos.length < PAGINA);
      } catch (e) {
        setErro(tratarErro(e));
      } finally {
        setCarregando(false);
      }
    },
    [conta, ip, setErro, tratarErro],
  );

  useEffect(() => {
    carregar(0);
  }, [carregar]);

  return (
    <div className="painel">
      <h2>Todas as consultas</h2>
      <div className="filtros">
        <div className="campo">
          <label htmlFor="filtro-conta">Conta</label>
          <select id="filtro-conta" value={conta} onChange={(e) => setConta(e.target.value)}>
            <option value="">Todas</option>
            {usuarios.map((u) => (
              <option key={u.tenant_id} value={u.tenant_id}>
                {u.email}
              </option>
            ))}
          </select>
        </div>
        <div className="campo">
          <label htmlFor="filtro-ip">IP de origem</label>
          <input id="filtro-ip" placeholder="todos" value={ip} onChange={(e) => setIp(e.target.value.trim())} />
        </div>
      </div>
      {itens.length === 0 && !carregando ? (
        <p className="mudo">Nenhuma consulta registrada.</p>
      ) : (
        <div className="tabela-wrap">
          <table className="tabela">
            <thead>
              <tr>
                <th>Quando</th>
                <th>Conta</th>
                <th>IP</th>
                <th>Consultado</th>
                <th>Finalidade</th>
                <th>Origem</th>
                <th>Resultado</th>
                <th className="num">Score</th>
              </tr>
            </thead>
            <tbody>
              {itens.map((a) => (
                <tr key={a.query_id}>
                  <td className="dado">{dataHoraBr(a.ocorrido_em)}</td>
                  <td className="dado" style={{ fontSize: 12 }}>
                    {porTenant[a.tenant_id]?.email ?? "chave administrativa"}
                  </td>
                  <td className="dado" style={{ fontSize: 12 }} title={a.user_agent ?? "sem user-agent"}>
                    {a.ip_origem ? (
                      <button className="link-ip" onClick={() => setIp(a.ip_origem!)}>
                        {a.ip_origem}
                      </button>
                    ) : (
                      <span className="mudo">não registrado</span>
                    )}
                  </td>
                  <td>
                    {a.cpf_mascarado && <div className="dado">{a.cpf_mascarado}</div>}
                    {a.nome_consultado && <div>{a.nome_consultado}</div>}
                  </td>
                  <td>{FINALIDADES[a.finalidade] ?? a.finalidade}</td>
                  <td>
                    <span className="etiqueta">{a.api_key_id ? "API" : "Painel"}</span>
                  </td>
                  <td>
                    <EtiquetaStatus status={a.status} />
                  </td>
                  <td className="num">{Math.round(a.score * 100)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {carregando && <p className="carregando">LENDO REGISTROS</p>}
      {!fim && !carregando && itens.length > 0 && (
        <button className="botao fantasma" style={{ marginTop: 16 }} onClick={() => carregar(itens.length)}>
          Carregar mais
        </button>
      )}
    </div>
  );
}

function Fontes({ tratarErro, setErro }: { tratarErro: (e: unknown) => string; setErro: (e: string | null) => void }) {
  const [fontes, setFontes] = useState<Fonte[]>([]);

  useEffect(() => {
    api
      .fontes()
      .then(setFontes)
      .catch((e) => setErro(tratarErro(e)));
  }, [tratarErro, setErro]);

  const tom = (status?: string) => (status === "erro" ? "sangue" : status === "rodando" ? "brasa" : "osso");

  return (
    <div className="fontes-lista" style={{ marginTop: 0 }}>
      {fontes.map((f) => (
        <div key={f.source_id} className="fonte-item">
          <span className="uf-mini">{f.uf}</span>
          <div className="desc">
            {f.descricao}
            <small>
              {f.source_id} · {f.cidade}
              {f.ultima_coleta?.fim ? ` · última coleta ${dataHoraBr(f.ultima_coleta.fim)}` : ""}
              {f.ultima_coleta?.entradas_publicadas !== undefined
                ? ` · ${f.ultima_coleta.entradas_publicadas} entradas`
                : ""}
            </small>
            {f.ultima_coleta?.status === "erro" && <small className="erro-fonte">{f.ultima_coleta.erro}</small>}
          </div>
          <span className={`etiqueta ${tom(f.ultima_coleta?.status)}`}>
            <span className="ponto" />
            {f.ultima_coleta ? f.ultima_coleta.status : "aguardando"}
          </span>
        </div>
      ))}
    </div>
  );
}
