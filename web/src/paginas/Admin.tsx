import { useCallback, useEffect, useMemo, useState } from "react";
import { Alerta, api, AuditEntryGeral, Fonte, UsuarioAdmin, UsuarioAdminIn } from "../api";
import { EtiquetaStatus } from "../componentes";
import { FINALIDADES } from "../dados";
import { dataHoraBr } from "../util";

type Aba = "alertas" | "usuarios" | "auditoria" | "fontes";
type Props = { tratarErro: (e: unknown) => string };

const LIMITES: [string, number | null][] = [
  ["Padrão (50)", null],
  ["200 por dia", 200],
  ["1.000 por dia", 1000],
  ["Ilimitado", 0],
];

export default function Admin({ tratarErro }: Props) {
  const [aba, setAba] = useState<Aba>("alertas");
  const [usuarios, setUsuarios] = useState<UsuarioAdmin[]>([]);
  const [alertas, setAlertas] = useState<Alerta[]>([]);
  const [filtroConta, setFiltroConta] = useState("");
  const [filtroIp, setFiltroIp] = useState("");
  const [erro, setErro] = useState<string | null>(null);

  const carregarUsuarios = useCallback(
    () =>
      api
        .usuarios()
        .then(setUsuarios)
        .catch((e) => setErro(tratarErro(e))),
    [tratarErro],
  );

  const carregarAlertas = useCallback(
    () =>
      api
        .alertas()
        .then(setAlertas)
        .catch((e) => setErro(tratarErro(e))),
    [tratarErro],
  );

  useEffect(() => {
    carregarUsuarios();
    carregarAlertas();
  }, [carregarUsuarios, carregarAlertas]);

  function verConsultas(alerta: Alerta) {
    setFiltroConta(alerta.tenant_id ?? "");
    setFiltroIp(alerta.ip ?? "");
    setAba("auditoria");
  }

  const pendentes = usuarios.filter((u) => !u.liberado && u.ativo).length;

  return (
    <>
      <div className="titulo-pagina">
        <h1>Administração</h1>
        <p>Visível só para administradoras.</p>
      </div>
      <div className="abas abas-pagina" role="tablist">
        <button role="tab" aria-selected={aba === "alertas"} onClick={() => setAba("alertas")}>
          Alertas{alertas.length > 0 && <span className="contador">{alertas.length}</span>}
        </button>
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
      {aba === "alertas" && (
        <Alertas
          alertas={alertas}
          usuarios={usuarios}
          recarregar={() => {
            carregarAlertas();
            carregarUsuarios();
          }}
          verConsultas={verConsultas}
          setErro={setErro}
          tratarErro={tratarErro}
        />
      )}
      {aba === "usuarios" && (
        <Usuarios usuarios={usuarios} recarregar={carregarUsuarios} setErro={setErro} tratarErro={tratarErro} />
      )}
      {aba === "auditoria" && (
        <AuditoriaGeral
          usuarios={usuarios}
          conta={filtroConta}
          setConta={setFiltroConta}
          ip={filtroIp}
          setIp={setFiltroIp}
          tratarErro={tratarErro}
          setErro={setErro}
        />
      )}
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
                      {u.nome} {u.admin && <span className="etiqueta sangue">admin</span>}{" "}
                      {u.mfa_ativo && <span className="etiqueta">MFA</span>}
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
                    {u.mfa_ativo && (
                      <button
                        className="botao fantasma"
                        onClick={() =>
                          alterar(
                            u,
                            { resetar_mfa: true },
                            `Resetar o MFA de ${u.email}? Ela vai precisar configurar de novo no próximo acesso.`,
                          )
                        }
                      >
                        Resetar MFA
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
  conta,
  setConta,
  ip,
  setIp,
  tratarErro,
  setErro,
}: {
  usuarios: UsuarioAdmin[];
  conta: string;
  setConta: (v: string) => void;
  ip: string;
  setIp: (v: string) => void;
  tratarErro: (e: unknown) => string;
  setErro: (e: string | null) => void;
}) {
  const [itens, setItens] = useState<AuditEntryGeral[]>([]);
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

function Alertas({
  alertas,
  usuarios,
  recarregar,
  verConsultas,
  setErro,
  tratarErro,
}: {
  alertas: Alerta[];
  usuarios: UsuarioAdmin[];
  recarregar: () => void;
  verConsultas: (a: Alerta) => void;
  setErro: (e: string | null) => void;
  tratarErro: (e: unknown) => string;
}) {
  const porTenant = useMemo(() => Object.fromEntries(usuarios.map((u) => [u.tenant_id, u])), [usuarios]);

  async function resolver(a: Alerta) {
    setErro(null);
    try {
      await api.alterarAlerta(a.id, "resolvido");
      recarregar();
    } catch (e) {
      setErro(tratarErro(e));
    }
  }

  async function bloquear(u: UsuarioAdmin, a: Alerta) {
    if (!window.confirm(`Bloquear ${u.email}? A sessão dela cai na hora e o alerta é marcado como resolvido.`)) return;
    setErro(null);
    try {
      await api.alterarUsuario(u.id, { ativo: false });
      await api.alterarAlerta(a.id, "resolvido");
      recarregar();
    } catch (e) {
      setErro(tratarErro(e));
    }
  }

  if (alertas.length === 0) {
    return (
      <div className="painel">
        <h2>Alertas</h2>
        <p className="mudo">Nenhuma suspeita de abuso em aberto. O detector avalia cada consulta em tempo real.</p>
      </div>
    );
  }

  return (
    <div className="alertas">
      {alertas.map((a) => {
        const u = a.tenant_id ? porTenant[a.tenant_id] : undefined;
        return (
          <article key={a.id} className={`alerta-card ${a.severidade}`}>
            <div className="alerta-topo">
              <span className={`etiqueta ${a.severidade === "alta" ? "sangue" : "brasa"}`}>
                <span className="ponto" />
                {a.severidade}
              </span>
              <span className="dado mudo" style={{ fontSize: 12 }}>
                {dataHoraBr(a.criado_em)}
              </span>
            </div>
            <h3>{a.rotulo}</h3>
            <p>{a.descricao}</p>
            <p className="dado mudo" style={{ fontSize: 12 }}>
              {u ? `Conta: ${u.email}${u.ativo ? "" : " (já bloqueada)"}` : a.ip ? `IP: ${a.ip}` : "Conta sem cadastro de usuário"}
            </p>
            <div className="acoes-alerta">
              <button className="botao fantasma" onClick={() => verConsultas(a)}>
                Ver consultas
              </button>
              {u && u.ativo && !u.admin && (
                <button className="botao fantasma" onClick={() => bloquear(u, a)}>
                  Bloquear conta
                </button>
              )}
              <button className="botao fantasma" onClick={() => resolver(a)}>
                Marcar como resolvido
              </button>
            </div>
          </article>
        );
      })}
    </div>
  );
}
