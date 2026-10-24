import { useEffect, useMemo, useState } from "react";
import { api, Estatisticas, Fonte } from "../api";
import { CAPITAIS, LADRILHOS } from "../dados";
import { dataHoraBr, numero } from "../util";

const COBERTURA_ROTULO = { ativo: "Fonte ativa", pendente: "Fonte pendente", sem_fonte: "Sem fonte aberta" };

type Props = { tratarErro: (e: unknown) => string; admin: boolean };

export default function Cobertura({ tratarErro, admin }: Props) {
  const [stats, setStats] = useState<Estatisticas | null>(null);
  const [fontes, setFontes] = useState<Fonte[]>([]);
  const [erro, setErro] = useState<string | null>(null);
  const [uf, setUf] = useState("PR");

  useEffect(() => {
    // A lista de fontes é interna: só administradores recebem.
    Promise.all([api.estatisticas(), admin ? api.fontes() : Promise.resolve([] as Fonte[])])
      .then(([s, f]) => {
        setStats(s);
        setFontes(f);
        if (s.por_uf[0]) setUf(s.por_uf[0].uf);
      })
      .catch((e) => setErro(tratarErro(e)));
  }, [tratarErro, admin]);

  const porUf = useMemo(() => Object.fromEntries((stats?.por_uf ?? []).map((u) => [u.uf, u])), [stats]);
  const maximo = Math.max(1, ...(stats?.por_uf ?? []).map((u) => u.total));
  const ativas = Object.values(CAPITAIS).filter((c) => c.cobertura === "ativo").length;
  const selecionada = CAPITAIS[uf];
  const dadosUf = porUf[uf];
  const fontesDaUf = fontes.filter((f) => f.uf === uf);

  return (
    <>
      <div className="titulo-pagina">
        <h1>Cobertura</h1>
        <p>O que a base enxerga hoje, capital por capital.</p>
      </div>
      {erro && <div className="alerta">{erro}</div>}

      <div className="kpis">
        <div className="painel kpi">
          <div className="rotulo">Registros de óbito</div>
          <div className="valor vivo">{stats ? numero(stats.total) : "..."}</div>
          <div className="sub">pessoas únicas após deduplicação</div>
        </div>
        <div className="painel kpi">
          <div className="rotulo">Capitais com fonte</div>
          <div className="valor">
            {ativas}
            <span className="mudo" style={{ fontSize: 18 }}>
              /27
            </span>
          </div>
          <div className="sub">as demais dependem de LAI ou parceria</div>
        </div>
        <div className="painel kpi">
          <div className="rotulo">Estados com registros</div>
          <div className="valor">{stats ? stats.por_uf.length : "..."}</div>
          <div className="sub">de 27 unidades da federação</div>
        </div>
        <div className="painel kpi">
          <div className="rotulo">Última atualização</div>
          <div className="valor" style={{ fontSize: 20, marginTop: 14 }}>
            {stats?.atualizado_em ? dataHoraBr(stats.atualizado_em) : "..."}
          </div>
        </div>
      </div>

      <div className="cobertura">
        <div className="painel">
          <h2>Mapa de cobertura</h2>
          <div className="mapa" role="list">
            {Object.entries(LADRILHOS).map(([sigla, [col, lin]]) => {
              const info = CAPITAIS[sigla];
              const total = porUf[sigla]?.total ?? 0;
              const intensidade = total ? 0.25 + 0.75 * Math.sqrt(total / maximo) : 0;
              return (
                <button
                  key={sigla}
                  role="listitem"
                  className={`uf ${info.cobertura} ${uf === sigla ? "selecionada" : ""}`}
                  style={{
                    gridColumn: col + 1,
                    gridRow: lin + 1,
                    ...(total ? { background: `rgba(255, 42, 61, ${intensidade})` } : {}),
                  }}
                  onClick={() => setUf(sigla)}
                  aria-label={`${sigla}, ${info.capital}: ${numero(total)} registros, ${COBERTURA_ROTULO[info.cobertura]}`}
                >
                  {sigla}
                  {total > 0 && <small>{total >= 1000 ? `${(total / 1000).toFixed(1)}k` : total}</small>}
                </button>
              );
            })}
          </div>
          <div className="legenda">
            <span>
              <i style={{ background: "var(--sangue)" }} /> registros (mais escuro, menos)
            </span>
            <span>
              <i style={{ background: "repeating-linear-gradient(45deg,#120607 0 3px,#2a0e10 3px 6px)" }} /> fonte
              pendente
            </span>
            <span>
              <i style={{ background: "#0b0304" }} /> sem fonte aberta
            </span>
          </div>
        </div>

        <div className="painel detalhe-uf">
          <h2>Detalhe</h2>
          <h3>{uf}</h3>
          <p className="capital">
            {selecionada.capital} · {COBERTURA_ROTULO[selecionada.cobertura]}
          </p>
          <div className="kpi" style={{ padding: 0 }}>
            <div className="rotulo">Registros no estado</div>
            <div className="valor vivo">{numero(dadosUf?.total ?? 0)}</div>
          </div>
          {admin && fontesDaUf.length > 0 && (
            <p style={{ marginTop: 14 }}>
              <span className="mudo">Fontes (visível só para administração): </span>
              {fontesDaUf.map((f) => f.descricao).join("; ")}
            </p>
          )}
          {selecionada.cobertura !== "ativo" && (
            <div className="alerta brando" style={{ marginTop: 14 }}>
              Sem fonte web aberta suficiente. A cobertura desta capital depende de pedido via LAI ou parceria com
              cemitérios e funerárias.
            </div>
          )}
          {dadosUf && (
            <ul className="cidades">
              {Object.entries(dadosUf.cidades)
                .sort((a, b) => b[1] - a[1])
                .map(([cidade, n]) => (
                  <li key={cidade}>
                    <span>{cidade}</span>
                    <span className="dado">{numero(n)}</span>
                  </li>
                ))}
            </ul>
          )}
        </div>
      </div>

    </>
  );
}
