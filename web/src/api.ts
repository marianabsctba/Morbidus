// Cliente do gateway. O painel usa a sessão (cookie HttpOnly); API keys são para integrações.

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
  ultima_coleta: { status: string; entradas_publicadas?: number; fim?: string } | null;
}

export interface Conta {
  nome: string;
  email: string;
  organizacao: string | null;
  uso_pretendido: UsoPretendido;
  limite_diario: number;
  consultas_hoje: number;
  criado_em: string;
}

export interface CadastroIn {
  nome: string;
  email: string;
  senha: string;
  organizacao?: string;
  uso_pretendido: UsoPretendido;
  aceite_termos: boolean;
}

export interface ApiKey {
  id: string;
  nome: string;
  prefixo: string;
  criado_em: string;
  revogada_em: string | null;
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
  cadastrar: (body: CadastroIn) => chamar<{ verificacao_necessaria: boolean }>("/v1/contas", json("POST", body)),
  verificar: (token: string) => chamar<{ ok: boolean }>("/v1/contas/verificar", json("POST", { token })),
  entrar: (email: string, senha: string) => chamar<{ nome: string }>("/v1/sessao", json("POST", { email, senha })),
  sair: () => chamar<void>("/v1/sessao", json("DELETE")),
  conta: () => chamar<Conta>("/v1/conta"),
  chaves: () => chamar<ApiKey[]>("/v1/conta/api-keys"),
  gerarChave: (nome: string) => chamar<ApiKey & { chave: string }>("/v1/conta/api-keys", json("POST", { nome })),
  revogarChave: (id: string) => chamar<void>(`/v1/conta/api-keys/${id}`, json("DELETE")),
  consultar: (body: ConsultaIn) => chamar<ConsultaOut>("/v1/consultas", json("POST", body)),
  auditoria: (offset = 0, limit = 25) => chamar<AuditEntry[]>(`/v1/auditoria?limit=${limit}&offset=${offset}`),
  estatisticas: () => chamar<Estatisticas>("/v1/estatisticas"),
  fontes: () => chamar<Fonte[]>("/v1/sources"),
};
