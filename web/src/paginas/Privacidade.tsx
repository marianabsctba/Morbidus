import { FormEvent, useState } from "react";
import { api, TipoSolicitacao } from "../api";
import { Marca } from "../componentes";

// Ao mudar o texto de forma relevante, suba a versão aqui e em TERMOS_VERSAO do identity-svc:
// todas as contas precisarão aceitar de novo antes de consultar.
export const VERSAO = "2026-10-24";
export const CONTROLADOR = "BeSafe Academy";
// LGPD, art. 41, §1º: identidade e canal do encarregado públicos. O canal é o formulário abaixo.
export const ENCARREGADA = "Mariana B., advogada";

export default function Privacidade({ aoVoltar }: { aoVoltar?: () => void }) {
  return (
    <main className="documento">
      <header>
        <Marca />
        <h1>Política de Privacidade e Termos de Uso</h1>
        <p className="mudo">Versão de {VERSAO.split("-").reverse().join("/")}</p>
      </header>

      <section>
        <h2>1. Quem somos</h2>
        <p>
          O MORBiDus é uma plataforma gratuita e de código aberto de prevenção à fraude com identidades de pessoas
          falecidas (Death Identity Fraud Prevention). É operado pela {CONTROLADOR}, que é a controladora dos dados
          tratados aqui. A encarregada de proteção de dados (DPO) é {ENCARREGADA}. Para falar com ela, use o{" "}
          <a href="#encarregado">formulário no fim desta página</a>.
        </p>
      </section>

      <section>
        <h2>2. Que dados tratamos</h2>
        <h3>2.1 Registros de óbito</h3>
        <p>
          Coletamos, de fontes públicas na internet (serviços funerários, cemitérios, funerárias e jornais), apenas os
          dados necessários para identificar um óbito: nome da pessoa falecida, idade, datas de nascimento, falecimento
          e sepultamento, cidade, local do sepultamento e o endereço da fonte. Respeitamos o arquivo robots.txt e os
          termos de uso de cada fonte. Não guardamos nomes de familiares, endereço residencial, profissão, causa da morte
          nem o texto dos obituários. As páginas coletadas ficam guardadas por no máximo 30 dias, só para corrigir
          falhas de leitura.
        </p>
        <h3>2.2 Dados de quem usa a plataforma</h3>
        <ul>
          <li>Cadastro: nome, e-mail, organização (opcional) e finalidade de uso declarada.</li>
          <li>Senha, guardada apenas como resumo criptográfico; e, se ativado, o segredo do MFA, guardado cifrado.</li>
          <li>
            Registros de acesso de cada consulta: data e hora, endereço IP e identificação do navegador (user-agent).
          </li>
          <li>
            Cada consulta: finalidade, nome consultado, CPF consultado (guardado mascarado e em resumo criptográfico,
            nunca por inteiro) e o resultado.
          </li>
          <li>Registro do aceite deste documento: versão, data e IP.</li>
        </ul>
      </section>

      <section>
        <h2>3. Para que usamos e com que base legal (LGPD)</h2>
        <ul>
          <li>
            Indicar se uma identidade pertence a pessoa falecida, para prevenir fraude: legítimo interesse (art. 7º, IX)
            e, quando a consulta for para concessão de crédito, proteção do crédito (art. 7º, X).
          </li>
          <li>Manter a sua conta e prestar o serviço: execução de contrato (art. 7º, V).</li>
          <li>
            Guardar os registros de acesso: cumprimento de obrigação legal, pelo prazo mínimo do Marco Civil da Internet
            (Lei 12.965/2014, art. 15).
          </li>
          <li>
            Detectar abuso da plataforma (consultas em massa, varredura de nomes, uso de várias contas pelo mesmo IP):
            legítimo interesse e segurança.
          </li>
        </ul>
      </section>

      <section>
        <h2>4. Com quem compartilhamos</h2>
        <ul>
          <li>Não vendemos nem cedemos dados a ninguém.</li>
          <li>
            Quando várias instituições consultam a mesma pessoa falecida em poucos dias, avisamos essas instituições de
            que a identidade está sendo muito consultada, sem revelar quem consultou.
          </li>
          <li>
            Endereços IP de contas cujo abuso foi confirmado por nossa equipe podem ser compartilhados com equipes de
            segurança parceiras, em formato de inteligência de ameaças (STIX/TAXII, classificação TLP:AMBER).
          </li>
          <li>Autoridades, quando houver ordem judicial ou obrigação legal.</li>
          <li>
            Fornecedores que operam a infraestrutura: hospedagem (Contabo, servidores na França), rede e proteção
            (Cloudflare, Estados Unidos) e envio de e-mail (GoDaddy, Estados Unidos). Isso caracteriza transferência
            internacional de dados, feita com esses provedores para a prestação do serviço (LGPD, art. 33).
          </li>
        </ul>
      </section>

      <section>
        <h2>5. Por quanto tempo guardamos</h2>
        <ul>
          <li>Conta: enquanto existir. Ao encerrar, os dados de cadastro são apagados.</li>
          <li>Consultas, registros de acesso e alertas: 2 anos, e depois são apagados automaticamente.</li>
          <li>Páginas coletadas das fontes: 30 dias.</li>
          <li>
            Registros de óbito: enquanto forem úteis para prevenir fraude, que pode acontecer anos depois da morte.
            Podem ser corrigidos ou removidos a pedido (item 6).
          </li>
          <li>Cópias de segurança: até 14 dias.</li>
          <li>Pedidos feitos ao encarregado: até 5 anos, para comprovar que foram atendidos.</li>
        </ul>
      </section>

      <section>
        <h2>6. Seus direitos</h2>
        <p>
          Você pode pedir confirmação de tratamento, acesso, correção, anonimização, eliminação, portabilidade e
          informação sobre compartilhamento, além de revogar consentimentos e se opor a tratamentos (LGPD, art. 18).
          Familiares de pessoas falecidas podem pedir a correção ou a remoção de um registro de óbito. Faça o pedido
          pelo <a href="#encarregado">formulário do encarregado</a>: você recebe um número de protocolo e a resposta em
          até 15 dias. Você também pode reclamar à Autoridade Nacional de Proteção de Dados (ANPD).
        </p>
      </section>

      <section>
        <h2>7. Segurança</h2>
        <p>
          Conexão sempre cifrada, senhas guardadas só como resumo criptográfico, verificação em duas etapas obrigatória
          para a administração, limite diário de consultas, registro imutável de todas as consultas e detecção
          automática de abuso. Usamos apenas o cookie de sessão, essencial para o login, e uma preferência visual guardada
          no seu navegador. Não usamos cookies de publicidade nem de rastreamento.
        </p>
      </section>

      <section>
        <h2>8. Termos de uso</h2>
        <ul>
          <li>
            Use o MORBiDus só para prevenir fraude ou para pesquisa. Toda consulta exige uma finalidade e fica registrada.
          </li>
          <li>
            É proibido usar a plataforma para expor, contatar, assediar ou prejudicar familiares de pessoas falecidas,
            para revender ou republicar dados, para consultar em massa ou de forma automatizada, ou para cometer fraude.
          </li>
          <li>
            O resultado é um indicador de risco. Registros vindos de obituários não têm CPF e podem coincidir com
            homônimos: confirme em fonte oficial antes de qualquer decisão.
          </li>
          <li>
            A base não cobre todos os óbitos do país. "Nada consta" não prova que a pessoa está viva.
          </li>
          <li>
            Podemos suspender ou encerrar contas que violem estes termos, e comunicar autoridades quando houver indício
            de crime.
          </li>
          <li>
            O serviço é gratuito e oferecido como está, sem garantia de disponibilidade. O código é aberto e está em
            github.com/marianabsctba/Morbidus.
          </li>
        </ul>
      </section>

      <section>
        <h2>9. Mudanças</h2>
        <p>
          Se este documento mudar de forma relevante, a nova versão será mostrada no seu próximo acesso e precisará ser
          aceita antes de você continuar consultando.
        </p>
      </section>

      <FormEncarregado />

      {aoVoltar && (
        <button className="botao" onClick={aoVoltar} style={{ marginTop: 12 }}>
          Voltar
        </button>
      )}
    </main>
  );
}


const TIPOS: [TipoSolicitacao, string][] = [
  ["remocao_registro_obito", "Correção ou remoção de registro de óbito de familiar"],
  ["acesso", "Acesso aos meus dados"],
  ["correcao", "Correção de dados"],
  ["eliminacao", "Eliminação dos meus dados"],
  ["informacao", "Informação sobre tratamento ou compartilhamento"],
  ["outro", "Outro assunto"],
];

function FormEncarregado() {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [tipo, setTipo] = useState<TipoSolicitacao | "">("");
  const [mensagem, setMensagem] = useState("");
  const [site, setSite] = useState("");
  const [protocolo, setProtocolo] = useState<string | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!tipo) return;
    setErro(null);
    setEnviando(true);
    try {
      const r = await api.solicitar({ nome, email, tipo, mensagem, site: site || undefined });
      setProtocolo(r.protocolo);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível enviar");
    } finally {
      setEnviando(false);
    }
  }

  return (
    <section id="encarregado" className="painel" style={{ marginTop: 40 }}>
      <h2 style={{ border: 0, margin: "0 0 14px" }}>10. Fale com o encarregado (DPO)</h2>
      {protocolo ? (
        <div className="chave-nova" role="status">
          <p>
            Pedido recebido. Seu protocolo é <strong className="dado">{protocolo}</strong>. Enviamos a confirmação para o
            seu e-mail e respondemos em até 15 dias.
          </p>
        </div>
      ) : (
        <form onSubmit={enviar}>
          <div className="linha">
            <div className="campo">
              <label htmlFor="dpo-nome">Seu nome</label>
              <input id="dpo-nome" autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} required />
            </div>
            <div className="campo">
              <label htmlFor="dpo-email">E-mail para resposta</label>
              <input id="dpo-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
            </div>
          </div>
          <div className="campo">
            <label htmlFor="dpo-tipo">Pedido</label>
            <select id="dpo-tipo" value={tipo} onChange={(e) => setTipo(e.target.value as TipoSolicitacao)} required>
              <option value="" disabled>
                Selecione
              </option>
              {TIPOS.map(([valor, rotulo]) => (
                <option key={valor} value={valor}>
                  {rotulo}
                </option>
              ))}
            </select>
          </div>
          <div className="campo">
            <label htmlFor="dpo-msg">Mensagem</label>
            <textarea
              id="dpo-msg"
              rows={6}
              value={mensagem}
              onChange={(e) => setMensagem(e.target.value)}
              placeholder="Conte o que você precisa. Para registro de óbito, informe o nome da pessoa e a cidade."
              required
            />
          </div>
          {/* Armadilha para robôs: escondida de pessoas e de leitores de tela. */}
          <input
            className="armadilha"
            tabIndex={-1}
            autoComplete="off"
            aria-hidden="true"
            value={site}
            onChange={(e) => setSite(e.target.value)}
          />
          {erro && (
            <div className="alerta" role="alert" style={{ marginBottom: 16 }}>
              {erro}
            </div>
          )}
          <button className="botao" disabled={enviando || !tipo || mensagem.trim().length < 10}>
            {enviando ? "Enviando..." : "Enviar ao encarregado"}
          </button>
        </form>
      )}
    </section>
  );
}
