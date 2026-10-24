// Cliente do gateway. O painel usa a sessão (cookie HttpOnly); não há acesso por API key.

export type Status = "obito_confirmado" | "sinal_forte" | "sinal_fraco" | "sem_registro";

export type Finalidade =
  | "onboarding"
  | "concessao_credito"
  | "prevencao_fraude"
  | "pagamento_beneficio"
  | "sinistro_seguro";

export type UsoPretendido = Finalidade | "pesquisa";

export interface ConsultaIn {
  cpf?: string;
  nome?: string;
  data_nascimento?: string;
  cidade?: string;
  uf?: string;
  finalidade: Finalidade;
}

export interface Evidencia {
  tipo: "oficial" | "obituario";
  fonte: string;
  score: number;
  detalhes: {
    nome?: string;
    idade?: number | null;
    data_nascimento?: string | null;
    data_falecimento?: string | null;
    cidade?: string;
    uf?: string;
    fontes?: string[];
    motivos?: string[];
    provider?: string;
    ano_obito?: number | null;
  };
}

export interface ConsultaOut {
  consulta_id: string;
  status: Status;
  score: number;
  evidencias: Evidencia[];
  fontes_indisponiveis: string[];
  aviso: string | null;
  alerta_coletivo: { outras_instituicoes: number; janela_dias: number; mensagem: string } | null;
}

export type TipoSolicitacao =
  | "acesso"
  | "correcao"
  | "eliminacao"
  | "remocao_registro_obito"
  | "informacao"
  | "outro";

export interface Solicitacao {
  id: string;
  protocolo: string;
  nome: string;
  email: string;
  tipo: TipoSolicitacao;
  rotulo: string;
  mensagem: string;
  status: "aberta" | "atendida";
  criado_em: string;
  atendido_em: string | null;
  observacao: string | null;
}

export interface Canario {
  nome: string;
  cidade: string;
  uf: string;
  data_nascimento: string | null;
  data_falecimento: string | null;
}

export interface AuditEntry {
  query_id: string;
  api_key_id: string | null;
  finalidade: Finalidade;
  cpf_mascarado: string | null;
  nome_consultado: string | null;
  status: Status;
  score: number;
  fontes_consultadas: string[];
  ocorrido_em: string;
}

export interface Estatisticas {
  total: number;
  por_uf: { uf: string; total: number; cidades: Record<string, number> }[];
  atualizado_em: string | null;
}

export interface Fonte {
  source_id: string;
  cidade: string;
  uf: string;
  descricao: string;
  ultima_coleta: { status: string; entradas_publicadas?: number; fim?: string; erro?: string } | null;
}

export interface Conta {
  nome: string;
  email: string;
  organizacao: string | null;
  uso_pretendido: UsoPretendido;
  limite_diario: number;
  consultas_hoje: number;
  criado_em: string;
  admin: boolean;
  mfa_ativo: boolean;
  aceite_pendente: boolean;
  termos_versao: string;
}

export interface UsuarioAdmin {
  id: string;
  tenant_id: string;
  nome: string;
  email: string;
  organizacao: string | null;
  uso_pretendido: UsoPretendido;
  liberado: boolean;
  ativo: boolean;
  admin: boolean;
  mfa_ativo: boolean;
  limite_diario: number;
  consultas_hoje: number;
  criado_em: string;
}

export type UsuarioAdminIn = Partial<Pick<UsuarioAdmin, "liberado" | "ativo" | "admin">> & {
  limite_diario?: number | null;
  resetar_mfa?: boolean;
};

export interface Alerta {
  id: string;
  regra: string;
  rotulo: string;
  severidade: "alta" | "media";
  tenant_id: string | null;
  ip: string | null;
  descricao: string;
  evidencias: Record<string, number>;
  criado_em: string;
  status: "aberto" | "resolvido" | "confirmado";
  resolvido_em: string | null;
}

export type RespostaLogin = { mfa: false; nome: string } | { mfa: true; desafio: string };

export interface AuditEntryGeral extends AuditEntry {
  tenant_id: string;
  ip_origem: string | null;
  user_agent: string | null;
}

export interface CadastroIn {
  nome: string;
  email: string;
  senha: string;
  organizacao?: string;
  uso_pretendido: UsoPretendido;
  aceite_termos: boolean;
}

export class NaoAutorizado extends Error {}

async function chamar<T>(caminho: string, init: RequestInit = {}): Promise<T> {
  const resp = await fetch(caminho, {
    credentials: "same-origin",
    ...init,
    headers: { "Content-Type": "application/json", ...(init.headers ?? {}) },
  });
  if (resp.status === 401) throw new NaoAutorizado("Sua sessão expirou. Entre de novo.");
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    const detalhe = Array.isArray(corpo.detail)
      ? corpo.detail.map((d: { msg: string }) => d.msg.replace(/^Value error, /, "")).join("; ")
      : corpo.detail;
    throw new Error(detalhe || `Erro ${resp.status}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const api = {
  cadastrar: (body: CadastroIn) => chamar<{ verificacao_necessaria: boolean; aprovacao_necessaria: boolean }>("/v1/contas", json("POST", body)),
  verificar: (token: string) => chamar<{ ok: boolean }>("/v1/contas/verificar", json("POST", { token })),
  entrar: (email: string, senha: string) => chamar<RespostaLogin>("/v1/sessao", json("POST", { email, senha })),
  entrarMfa: (desafio: string, codigo: string) =>
    chamar<{ nome: string }>("/v1/sessao/mfa", json("POST", { desafio, codigo })),
  mfaIniciar: () => chamar<{ segredo: string; uri: string }>("/v1/conta/mfa/iniciar", json("POST")),
  mfaAtivar: (codigo: string) =>
    chamar<{ codigos_recuperacao: string[] }>("/v1/conta/mfa/ativar", json("POST", { codigo })),
  mfaDesativar: (codigo: string) => chamar<void>("/v1/conta/mfa/desativar", json("POST", { codigo })),
  sair: () => chamar<void>("/v1/sessao", json("DELETE")),
  conta: () => chamar<Conta>("/v1/conta"),
  aceitarTermos: () => chamar<void>("/v1/conta/aceite", json("POST")),
  // Público: formulário do encarregado (DPO).
  solicitar: (body: { nome: string; email: string; tipo: TipoSolicitacao; mensagem: string; site?: string }) =>
    chamar<{ protocolo: string; prazo_dias: number }>("/v1/privacidade/solicitacoes", json("POST", body)),
  consultar: (body: ConsultaIn) => chamar<ConsultaOut>("/v1/consultas", json("POST", body)),
  auditoria: (offset = 0, limit = 25) => chamar<AuditEntry[]>(`/v1/auditoria?limit=${limit}&offset=${offset}`),
  estatisticas: () => chamar<Estatisticas>("/v1/estatisticas"),
  // Só administradores.
  fontes: () => chamar<Fonte[]>("/v1/sources"),
  canarios: () => chamar<Canario[]>("/v1/canarios"),
  solicitacoes: () => chamar<Solicitacao[]>("/v1/conta/admin/solicitacoes"),
  atualizarSolicitacao: (id: string, status: Solicitacao["status"], observacao?: string) =>
    chamar<Solicitacao>(`/v1/conta/admin/solicitacoes/${id}`, json("PATCH", { status, observacao })),
  plantarCanarios: (quantidade: number) => chamar<Canario[]>("/v1/canarios", json("POST", { quantidade })),
  usuarios: () => chamar<UsuarioAdmin[]>("/v1/conta/admin/usuarios"),
  alterarUsuario: (id: string, body: UsuarioAdminIn) =>
    chamar<UsuarioAdmin>(`/v1/conta/admin/usuarios/${id}`, json("PATCH", body)),
  auditoriaGeral: (offset = 0, limit = 50, filtros: { tenantId?: string; ip?: string } = {}) => {
    const q = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (filtros.tenantId) q.set("tenant_id", filtros.tenantId);
    if (filtros.ip) q.set("ip", filtros.ip);
    return chamar<AuditEntryGeral[]>(`/v1/auditoria/geral?${q}`);
  },
  alertas: (status: Alerta["status"] = "aberto") => chamar<Alerta[]>(`/v1/alertas?status=${status}`),
  alterarAlerta: (id: string, status: Alerta["status"]) =>
    chamar<Alerta>(`/v1/alertas/${id}`, json("PATCH", { status })),
};
