import { FormEvent, useState } from "react";
import { api, UsoPretendido } from "../api";
import { Marca } from "../componentes";
import { FINALIDADES } from "../dados";

const USOS: Record<UsoPretendido, string> = { ...FINALIDADES, pesquisa: "Pesquisa acadêmica / jornalística" };

export default function Entrada({ aoEntrar }: { aoEntrar: () => void }) {
  const [modo, setModo] = useState<"entrar" | "cadastrar">("entrar");
  const [aviso, setAviso] = useState<string | null>(null);

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

        <div className="painel">
          <div className="abas" role="tablist">
            <button role="tab" aria-selected={modo === "entrar"} onClick={() => setModo("entrar")}>
              Entrar
            </button>
            <button role="tab" aria-selected={modo === "cadastrar"} onClick={() => setModo("cadastrar")}>
              Criar conta
            </button>
          </div>
          {aviso && (
            <div className="alerta brando" role="status" style={{ marginBottom: 16 }}>
              {aviso}
            </div>
          )}
          {modo === "entrar" ? (
            <FormEntrar aoEntrar={aoEntrar} />
          ) : (
            <FormCadastro
              aoCadastrar={(verificar) => {
                setModo("entrar");
                setAviso(
                  verificar
                    ? "Conta criada. Enviamos um link de confirmação para o seu e-mail."
                    : "Conta criada. Já pode entrar.",
                );
              }}
            />
          )}
        </div>
        <p className="rodape-login">Gratuito e open source. Toda consulta exige finalidade e fica registrada.</p>
      </div>
    </main>
  );
}

function FormEntrar({ aoEntrar }: { aoEntrar: () => void }) {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      await api.entrar(email, senha);
      aoEntrar();
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível entrar");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <form onSubmit={enviar}>
      <div className="campo">
        <label htmlFor="email">E-mail</label>
        <input id="email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>
      <div className="campo">
        <label htmlFor="senha">Senha</label>
        <input
          id="senha"
          type="password"
          autoComplete="current-password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          required
        />
      </div>
      {erro && (
        <div className="alerta" role="alert" style={{ marginBottom: 16 }}>
          {erro}
        </div>
      )}
      <button className="botao largo" disabled={carregando || !email || !senha}>
        {carregando ? "Entrando..." : "Entrar"}
      </button>
    </form>
  );
}

function FormCadastro({ aoCadastrar }: { aoCadastrar: (verificar: boolean) => void }) {
  const [nome, setNome] = useState("");
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [organizacao, setOrganizacao] = useState("");
  const [uso, setUso] = useState<UsoPretendido | "">("");
  const [aceite, setAceite] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  const senhaCurta = senha.length > 0 && senha.length < 10;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!uso) return;
    setErro(null);
    setCarregando(true);
    try {
      const r = await api.cadastrar({
        nome,
        email,
        senha,
        organizacao: organizacao || undefined,
        uso_pretendido: uso,
        aceite_termos: aceite,
      });
      aoCadastrar(r.verificacao_necessaria);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível criar a conta");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <form onSubmit={enviar}>
      <div className="campo">
        <label htmlFor="c-nome">Nome</label>
        <input id="c-nome" autoComplete="name" value={nome} onChange={(e) => setNome(e.target.value)} required />
      </div>
      <div className="campo">
        <label htmlFor="c-email">E-mail</label>
        <input id="c-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </div>
      <div className="campo">
        <label htmlFor="c-senha">Senha</label>
        <input
          id="c-senha"
          type="password"
          autoComplete="new-password"
          value={senha}
          onChange={(e) => setSenha(e.target.value)}
          required
        />
        <span className={`dica ${senhaCurta ? "erro" : ""}`}>No mínimo 10 caracteres.</span>
      </div>
      <div className="campo">
        <label htmlFor="c-org">Organização (opcional)</label>
        <input id="c-org" autoComplete="organization" value={organizacao} onChange={(e) => setOrganizacao(e.target.value)} />
      </div>
      <div className="campo">
        <label htmlFor="c-uso">
          Para que vai usar <span className="obrig">*</span>
        </label>
        <select id="c-uso" value={uso} onChange={(e) => setUso(e.target.value as UsoPretendido)} required>
          <option value="" disabled>
            Selecione
          </option>
          {Object.entries(USOS).map(([valor, rotulo]) => (
            <option key={valor} value={valor}>
              {rotulo}
            </option>
          ))}
        </select>
      </div>
      <label className="aceite">
        <input type="checkbox" checked={aceite} onChange={(e) => setAceite(e.target.checked)} />
        <span>
          Vou usar o MORBiDus só para prevenir fraude ou para pesquisa, nunca para expor ou contatar familiares, e sei
          que minhas consultas ficam registradas.
        </span>
      </label>
      {erro && (
        <div className="alerta" role="alert" style={{ marginBottom: 16 }}>
          {erro}
        </div>
      )}
      <button className="botao largo" disabled={carregando || !aceite || !uso || senha.length < 10}>
        {carregando ? "Criando..." : "Criar conta"}
      </button>
    </form>
  );
}
