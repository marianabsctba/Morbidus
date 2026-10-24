import { useEffect } from "react";
import { Conta as ContaT } from "../api";
import { FINALIDADES } from "../dados";
import { dataHoraBr } from "../util";

type Props = { conta: ContaT; atualizar: () => void };

export default function Conta({ conta, atualizar }: Props) {
  useEffect(atualizar, [atualizar]);

  const ilimitado = conta.limite_diario === 0;
  const pct = ilimitado ? 0 : Math.min(100, (conta.consultas_hoje / conta.limite_diario) * 100);

  return (
    <>
      <div className="titulo-pagina">
        <h1>Minha conta</h1>
        <p>{conta.email}</p>
      </div>

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
            O limite renova à meia-noite (UTC). Toda consulta fica registrada na sua auditoria.
          </p>
        </div>
      </div>
    </>
  );
}
