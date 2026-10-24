import { useEffect, useState } from "react";
import { api, AuditEntry } from "../api";
import { EtiquetaStatus } from "../componentes";
import { FINALIDADES } from "../dados";
import { dataHoraBr } from "../util";

const PAGINA = 25;

export default function Auditoria({ tratarErro }: { tratarErro: (e: unknown) => string }) {
  const [itens, setItens] = useState<AuditEntry[]>([]);
  const [fim, setFim] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  async function carregar(offset: number) {
    setCarregando(true);
    try {
      const novos = await api.auditoria(offset, PAGINA);
      setItens((atual) => (offset === 0 ? novos : [...atual, ...novos]));
      setFim(novos.length < PAGINA);
    } catch (e) {
      setErro(tratarErro(e));
    } finally {
      setCarregando(false);
    }
  }

  useEffect(() => {
    carregar(0);
  }, []);

  return (
    <>
      <div className="titulo-pagina">
        <h1>Auditoria</h1>
        <p>Todas as consultas feitas com as chaves desta organização. O registro não pode ser alterado.</p>
      </div>
      {erro && <div className="alerta">{erro}</div>}
      <div className="painel">
        <h2>Trilha de consultas</h2>
        {itens.length === 0 && !carregando ? (
          <p className="mudo">Nenhuma consulta registrada ainda.</p>
        ) : (
          <div className="tabela-wrap">
            <table className="tabela">
              <thead>
                <tr>
                  <th>Quando</th>
                  <th>Consultado</th>
                  <th>Finalidade</th>
                  <th>Resultado</th>
                  <th className="num">Score</th>
                </tr>
              </thead>
              <tbody>
                {itens.map((a) => (
                  <tr key={a.query_id}>
                    <td className="dado">{dataHoraBr(a.ocorrido_em)}</td>
                    <td>
                      {a.cpf_mascarado && <div className="dado">{a.cpf_mascarado}</div>}
                      {a.nome_consultado && <div>{a.nome_consultado}</div>}
                    </td>
                    <td>{FINALIDADES[a.finalidade] ?? a.finalidade}</td>
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
    </>
  );
}
