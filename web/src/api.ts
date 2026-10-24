// Cliente do gateway. A API key fica no sessionStorage: some ao fechar a aba.

const CHAVE = "morbidus.apiKey";

export type Status = "obito_confirmado" | "sinal_forte" | "sinal_fraco" | "sem_registro";

export type Finalidade =
  | "onboarding"
  | "concessao_credito"
  | "prevencao_fraude"
  | "pagamento_beneficio"
  | "sinistro_seguro";

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

export class NaoAutorizado extends Error {}

export function getKey(): string | null {
  try {
    return sessionStorage.getItem(CHAVE);
  } catch {
    return null;
  }
}

export function setKey(key: string | null): void {
  try {
    if (key) sessionStorage.setItem(CHAVE, key);
    else sessionStorage.removeItem(CHAVE);
  } catch {
    // Navegação privada pode bloquear o storage; a sessão dura só a página.
  }
}

async function chamar<T>(caminho: string, init: RequestInit = {}, key = getKey()): Promise<T> {
  const resp = await fetch(caminho, {
    ...init,
    headers: { "Content-Type": "application/json", "X-API-Key": key ?? "", ...(init.headers ?? {}) },
  });
  if (resp.status === 401 || resp.status === 403) throw new NaoAutorizado("API key inválida ou revogada");
  if (!resp.ok) {
    const corpo = await resp.json().catch(() => ({}));
    const detalhe = Array.isArray(corpo.detail) ? corpo.detail.map((d: { msg: string }) => d.msg).join("; ") : corpo.detail;
    throw new Error(detalhe || `Erro ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  validarChave: (key: string) => chamar<Estatisticas>("/v1/estatisticas", {}, key),
  consultar: (body: ConsultaIn) => chamar<ConsultaOut>("/v1/consultas", { method: "POST", body: JSON.stringify(body) }),
  auditoria: (offset = 0, limit = 25) => chamar<AuditEntry[]>(`/v1/auditoria?limit=${limit}&offset=${offset}`),
  estatisticas: () => chamar<Estatisticas>("/v1/estatisticas"),
  fontes: () => chamar<Fonte[]>("/v1/sources"),
};
