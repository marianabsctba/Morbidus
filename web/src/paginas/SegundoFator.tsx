import { FormEvent, useMemo, useState } from "react";
import qrcode from "qrcode-generator";
import { api, Conta } from "../api";

type Props = { conta: Conta; atualizar: () => void; tratarErro: (e: unknown) => string };

function Qr({ texto }: { texto: string }) {
  // Gerado no navegador: o segredo nunca passa por serviço externo de QR.
  const svg = useMemo(() => {
    const qr = qrcode(0, "M");
    qr.addData(texto);
    qr.make();
    return qr.createSvgTag({ cellSize: 5, margin: 2, scalable: true });
  }, [texto]);
  return <div className="qr" role="img" aria-label="QR code do MFA" dangerouslySetInnerHTML={{ __html: svg }} />;
}

export default function SegundoFator({ conta, atualizar, tratarErro }: Props) {
  const [config, setConfig] = useState<{ segredo: string; uri: string } | null>(null);
  const [codigo, setCodigo] = useState("");
  const [recuperacao, setRecuperacao] = useState<string[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [carregando, setCarregando] = useState(false);

  async function iniciar() {
    setErro(null);
    try {
      setConfig(await api.mfaIniciar());
    } catch (e) {
      setErro(tratarErro(e));
    }
  }

  async function ativar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setCarregando(true);
    try {
      const r = await api.mfaAtivar(codigo.trim());
      setRecuperacao(r.codigos_recuperacao);
      setConfig(null);
      setCodigo("");
      atualizar();
    } catch (err) {
      setErro(tratarErro(err));
    } finally {
      setCarregando(false);
    }
  }

  async function desativar(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    try {
      await api.mfaDesativar(codigo.trim());
      setCodigo("");
      atualizar();
    } catch (err) {
      setErro(tratarErro(err));
    }
  }

  function baixarCodigos(codigos: string[]) {
    const texto = `MORBiDus: códigos de recuperação do MFA (${conta.email})\nCada código funciona uma única vez.\n\n${codigos.join("\n")}\n`;
    const url = URL.createObjectURL(new Blob([texto], { type: "text/plain" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "morbidus-codigos-recuperacao.txt";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="painel" style={{ marginTop: 28 }}>
      <h2>Verificação em duas etapas (MFA)</h2>
      {erro && (
        <div className="alerta" role="alert" style={{ marginBottom: 16 }}>
          {erro}
        </div>
      )}

      {recuperacao && (
        <div className="chave-nova" role="status">
          <p>
            MFA ativado. Guarde estes códigos de recuperação num lugar seguro: eles são a única forma de entrar se você
            perder o celular, e não serão mostrados de novo.
          </p>
          <ul className="codigos">
            {recuperacao.map((c) => (
              <li key={c} className="dado">
                {c}
              </li>
            ))}
          </ul>
          <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
            <button className="botao fantasma" onClick={() => baixarCodigos(recuperacao)}>
              Baixar .txt
            </button>
            <button className="botao fantasma" onClick={() => setRecuperacao(null)}>
              Já guardei
            </button>
          </div>
        </div>
      )}

      {conta.mfa_ativo && !recuperacao && (
        <>
          <p>
            <span className="etiqueta osso">
              <span className="ponto" />
              ativo
            </span>{" "}
            <span className="mudo">Todo login pede o código do aplicativo.</span>
          </p>
          {conta.admin ? (
            <p className="mudo" style={{ fontSize: 13 }}>
              Administradoras precisam manter o MFA ativo. Se perder o celular e os códigos de recuperação, outra
              administradora pode resetar o seu MFA.
            </p>
          ) : (
            <form className="gerar-chave" onSubmit={desativar}>
              <div className="campo" style={{ marginBottom: 0, flex: 1 }}>
                <label htmlFor="mfa-off">Código atual para desativar</label>
                <input id="mfa-off" inputMode="numeric" value={codigo} onChange={(e) => setCodigo(e.target.value)} />
              </div>
              <button className="botao fantasma" disabled={codigo.trim().length < 6}>
                Desativar MFA
              </button>
            </form>
          )}
        </>
      )}

      {!conta.mfa_ativo && !config && (
        <>
          {conta.admin && (
            <div className="alerta" style={{ marginBottom: 16 }}>
              Você é administradora: a área de Administração só abre depois que o MFA estiver ativo.
            </div>
          )}
          <p className="mudo">
            Protege a sua conta mesmo se a senha vazar. Funciona com Google Authenticator, Microsoft Authenticator,
            1Password e similares.
          </p>
          <button className="botao" onClick={iniciar}>
            Ativar MFA
          </button>
        </>
      )}

      {config && (
        <div className="mfa-config">
          <Qr texto={config.uri} />
          <form onSubmit={ativar}>
            <ol className="passos">
              <li>Abra o aplicativo autenticador e escaneie o QR code.</li>
              <li>
                Sem câmera? Digite a chave manualmente:
                <code className="segredo">{config.segredo.match(/.{1,4}/g)?.join(" ")}</code>
              </li>
              <li>Digite o código de 6 dígitos que aparecer no aplicativo.</li>
            </ol>
            <div className="campo">
              <label htmlFor="mfa-codigo">Código</label>
              <input
                id="mfa-codigo"
                className="codigo-mfa"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={codigo}
                onChange={(e) => setCodigo(e.target.value)}
              />
            </div>
            <div style={{ display: "flex", gap: 10 }}>
              <button className="botao" disabled={carregando || codigo.trim().length < 6}>
                {carregando ? "Conferindo..." : "Confirmar e ativar"}
              </button>
              <button type="button" className="botao fantasma" onClick={() => setConfig(null)}>
                Cancelar
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
