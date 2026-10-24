import { FormEvent, useState } from "react";
import { api, ConsultaOut, Evidencia, Finalidade } from "../api";
import { EtiquetaStatus, Medidor } from "../componentes";
import { FINALIDADES, STATUS, UFS } from "../dados";
import { cpfValido, dataBr, dominio, mascararCpf, soDigitos } from "../util";

type Props = { tratarErro: (e: unknown) => string };

export default function Consulta({ tratarErro }: Props) {
  const [cpf, setCpf] = useState("");
  const [nome, setNome] = useState("");
  const [nascimento, setNascimento] = useState("");
  const [cidade, setCidade] = useState("");
  const [uf, setUf] = useState("");
  const [finalidade, setFinalidade] = useState<Finalidade | "">("");
  const [resultado, setResultado] = useState<ConsultaOut | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const cpfDigitos = soDigitos(cpf);
  const cpfCompleto = cpfDigitos.length === 11;
  const cpfOk = cpfCompleto && cpfValido(cpf);
  const nomeOk = nome.trim().split(/\s+/).length >= 2;
  const podeConsultar = !!finalidade && (cpfOk || nomeOk) && !(cpfCompleto && !cpfOk) && !carregando;

  async function consultar(e: FormEvent) {
    e.preventDefault();
    if (!finalidade) return;
    setErro(null);
    setCarregando(true);
    try {
      const r = await api.consultar({
        finalidade,
        cpf: cpfOk ? cpfDigitos : undefined,
        nome: nomeOk ? nome.trim() : undefined,
        data_nascimento: nascimento || undefined,
        cidade: cidade.trim() || undefined,
        uf: uf || undefined,
      });
      setResultado(r);
    } catch (err) {
      setErro(tratarErro(err));
    } finally {
      setCarregando(false);
    }
  }

  return (
    <>
      <div className="titulo-pagina">
        <h1>Consulta</h1>
        <p>Verifique se uma identidade pertence a alguém que já morreu.</p>
      </div>

      <div className="consulta">
        <form className="painel" onSubmit={consultar} noValidate>
          <h2>Ficha de consulta</h2>

          <div className="campo">
            <label htmlFor="cpf">CPF</label>
            <input
              id="cpf"
              inputMode="numeric"
              placeholder="000.000.000-00"
              value={cpf}
              onChange={(e) => setCpf(mascararCpf(e.target.value))}
            />
            {cpfCompleto && (
              <span className={`dica ${cpfOk ? "ok" : "erro"}`}>
                {cpfOk ? "Dígitos verificadores conferem" : "CPF inválido"}
              </span>
            )}
          </div>

          <div className="ou">E / OU</div>

          <div className="campo">
            <label htmlFor="nome">Nome completo</label>
            <input id="nome" autoComplete="off" value={nome} onChange={(e) => setNome(e.target.value)} />
          </div>
          <div className="linha">
            <div className="campo">
              <label htmlFor="nasc">Nascimento</label>
              <input id="nasc" type="date" value={nascimento} onChange={(e) => setNascimento(e.target.value)} />
            </div>
            <div className="campo">
              <label htmlFor="uf">UF</label>
              <select id="uf" value={uf} onChange={(e) => setUf(e.target.value)}>
                <option value="">Todas</option>
                {UFS.map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </div>
          </div>
          <div className="campo">
            <label htmlFor="cidade">Cidade</label>
            <input id="cidade" value={cidade} onChange={(e) => setCidade(e.target.value)} />
          </div>

          <div className="campo">
            <label htmlFor="fin">
              Finalidade <span className="obrig">*</span>
            </label>
            <select id="fin" value={finalidade} onChange={(e) => setFinalidade(e.target.value as Finalidade)} required>
              <option value="" disabled>
                Selecione a base legal da consulta
              </option>
              {Object.entries(FINALIDADES).map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </select>
            <span className="dica">Fica registrada na trilha de auditoria.</span>
          </div>

          <button className="botao largo" disabled={!podeConsultar}>
            {carregando ? "Investigando..." : "Consultar"}
          </button>
        </form>

        <section aria-live="polite">
          {erro && (
            <div className="alerta" role="alert" style={{ marginBottom: 20 }}>
              {erro}
            </div>
          )}
          {resultado ? <Laudo r={resultado} /> : <LaudoVazio carregando={carregando} />}
        </section>
      </div>
    </>
  );
}

function LaudoVazio({ carregando }: { carregando: boolean }) {
  return (
    <div className="laudo-vazio">
      <div>
        <div className="simbolo">✝</div>
        {carregando ? (
          <p className="carregando">CRUZANDO REGISTROS</p>
        ) : (
          <>
            <p>Nenhum laudo aberto.</p>
            <p className="mudo">
              Informe um CPF para checar fontes oficiais, ou nome com data de nascimento e cidade para cruzar com
              obituários.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

function Laudo({ r }: { r: ConsultaOut }) {
  const s = STATUS[r.status];
  const oficiais = r.evidencias.filter((e) => e.tipo === "oficial").length;
  const obituarios = r.evidencias.length - oficiais;
  const [copiado, setCopiado] = useState(false);

  return (
    <div className={`laudo ${r.status}`} key={r.consulta_id}>
      <div className="cabeca-laudo">
        <div>
          <span className={`carimbo ${s.tom}`}>{s.carimbo}</span>
          <p className="resumo">
            <span className="dado">{oficiais}</span> evidência(s) oficial(is) ·{" "}
            <span className="dado">{obituarios}</span> obituário(s) compatível(is)
          </p>
          <div className="id-consulta">
            <span>
              Laudo <span className="dado">{r.consulta_id.slice(0, 12)}</span>
            </span>
            <button
              type="button"
              className="botao fantasma"
              onClick={() => {
                navigator.clipboard?.writeText(r.consulta_id);
                setCopiado(true);
                setTimeout(() => setCopiado(false), 1500);
              }}
            >
              {copiado ? "Copiado" : "Copiar ID"}
            </button>
          </div>
        </div>
        <Medidor valor={r.score} />
      </div>

      {r.aviso && <div className="alerta brando">{r.aviso}</div>}
      {r.fontes_indisponiveis.length > 0 && (
        <div className="alerta brando">
          Fontes indisponíveis nesta consulta: {r.fontes_indisponiveis.join(", ")}. O resultado pode estar incompleto.
        </div>
      )}

      {r.evidencias.length > 0 && (
        <div className="evidencias">
          {r.evidencias.map((e, i) => (
            <CartaoEvidencia key={`${e.fonte}-${i}`} e={e} />
          ))}
        </div>
      )}
    </div>
  );
}

function CartaoEvidencia({ e }: { e: Evidencia }) {
  const d = e.detalhes;
  if (e.tipo === "oficial") {
    return (
      <article className="evidencia">
        <div>
          <span className="etiqueta sangue">
            <span className="ponto" />
            Fonte oficial
          </span>
          <div className="nome" style={{ marginTop: 8 }}>
            Titular falecido
          </div>
        </div>
        <div className="score">{Math.round(e.score * 100)}</div>
        <div className="barra">
          <span style={{ width: `${e.score * 100}%` }} />
        </div>
        <dl>
          <div>
            <dt>Provedor</dt>
            <dd>{d.provider ?? e.fonte}</dd>
          </div>
          <div>
            <dt>Ano do óbito</dt>
            <dd>{d.ano_obito ?? "não informado"}</dd>
          </div>
        </dl>
      </article>
    );
  }
  return (
    <article className="evidencia">
      <div>
        <EtiquetaStatus status={e.score >= 0.85 ? "sinal_forte" : "sinal_fraco"} />
        <div className="nome" style={{ marginTop: 8 }}>
          {d.nome}
        </div>
      </div>
      <div className="score">{Math.round(e.score * 100)}</div>
      <div className="barra">
        <span style={{ width: `${e.score * 100}%` }} />
      </div>
      <dl>
        <div>
          <dt>Nascimento</dt>
          <dd>{dataBr(d.data_nascimento)}</dd>
        </div>
        <div>
          <dt>Falecimento</dt>
          <dd>{dataBr(d.data_falecimento)}</dd>
        </div>
        <div>
          <dt>Idade</dt>
          <dd>{d.idade ?? "?"}</dd>
        </div>
        <div>
          <dt>Local</dt>
          <dd>
            {d.cidade}/{d.uf}
          </dd>
        </div>
      </dl>
      {d.motivos && (
        <div className="motivos">
          {d.motivos.map((m) => (
            <span key={m} className="etiqueta">
              {m}
            </span>
          ))}
        </div>
      )}
      {d.fontes && d.fontes.length > 0 && (
        <div className="fontes">
          Fontes:{" "}
          {d.fontes.map((f, i) => (
            <span key={f}>
              {i > 0 && " · "}
              <a href={f} target="_blank" rel="noreferrer noopener">
                {dominio(f)}
              </a>
            </span>
          ))}
        </div>
      )}
    </article>
  );
}
