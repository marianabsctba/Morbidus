import type { Finalidade, Status } from "./api";

export const STATUS: Record<Status, { rotulo: string; carimbo: string; tom: "sangue" | "brasa" | "cinza" | "osso" }> = {
  obito_confirmado: { rotulo: "Óbito confirmado", carimbo: "ÓBITO CONFIRMADO", tom: "sangue" },
  sinal_forte: { rotulo: "Sinal forte", carimbo: "SINAL FORTE", tom: "brasa" },
  sinal_fraco: { rotulo: "Sinal fraco", carimbo: "SINAL FRACO", tom: "cinza" },
  sem_registro: { rotulo: "Sem registro", carimbo: "NADA CONSTA", tom: "osso" },
};

export const FINALIDADES: Record<Finalidade, string> = {
  onboarding: "Abertura de conta / onboarding",
  concessao_credito: "Concessão de crédito",
  prevencao_fraude: "Investigação de fraude",
  pagamento_beneficio: "Pagamento de benefício",
  sinistro_seguro: "Sinistro de seguro",
};

export type Cobertura = "ativo" | "pendente" | "sem_fonte";

// Situação de cada capital. Fonte: docs/fontes-obituarios.md.
export const CAPITAIS: Record<string, { capital: string; cobertura: Cobertura; fontes: string[] }> = {
  AC: { capital: "Rio Branco", cobertura: "sem_fonte", fontes: [] },
  AL: { capital: "Maceió", cobertura: "sem_fonte", fontes: [] },
  AP: { capital: "Macapá", cobertura: "sem_fonte", fontes: [] },
  AM: { capital: "Manaus", cobertura: "pendente", fontes: ["Santa Rita / São Francisco"] },
  BA: { capital: "Salvador", cobertura: "ativo", fontes: ["Cemitério Campo Santo", "Cemitério Bosque da Paz"] },
  CE: { capital: "Fortaleza", cobertura: "sem_fonte", fontes: [] },
  DF: { capital: "Brasília", cobertura: "ativo", fontes: ["Correio Braziliense"] },
  ES: { capital: "Vitória", cobertura: "pendente", fontes: ["A Gazeta (notórios)"] },
  GO: { capital: "Goiânia", cobertura: "sem_fonte", fontes: [] },
  MA: { capital: "São Luís", cobertura: "sem_fonte", fontes: [] },
  MT: { capital: "Cuiabá", cobertura: "sem_fonte", fontes: [] },
  MS: { capital: "Campo Grande", cobertura: "ativo", fontes: ["A Crítica"] },
  MG: { capital: "Belo Horizonte", cobertura: "pendente", fontes: ["Estado de Minas (notórios)"] },
  PA: { capital: "Belém", cobertura: "sem_fonte", fontes: [] },
  PB: { capital: "João Pessoa", cobertura: "sem_fonte", fontes: [] },
  PR: { capital: "Curitiba", cobertura: "ativo", fontes: ["Serviço Funerário Municipal"] },
  PE: { capital: "Recife", cobertura: "sem_fonte", fontes: [] },
  PI: { capital: "Teresina", cobertura: "sem_fonte", fontes: [] },
  RJ: { capital: "Rio de Janeiro", cobertura: "sem_fonte", fontes: [] },
  RN: { capital: "Natal", cobertura: "ativo", fontes: ["Grupo Leão e Vila"] },
  RS: { capital: "Porto Alegre", cobertura: "ativo", fontes: ["Grupo Angelus"] },
  RO: { capital: "Porto Velho", cobertura: "ativo", fontes: ["News Rondônia"] },
  RR: { capital: "Boa Vista", cobertura: "sem_fonte", fontes: [] },
  SC: { capital: "Florianópolis", cobertura: "ativo", fontes: ["Cemitério Jardim da Paz"] },
  SP: { capital: "São Paulo", cobertura: "ativo", fontes: ["Cemitério Israelita"] },
  SE: { capital: "Aracaju", cobertura: "sem_fonte", fontes: [] },
  TO: { capital: "Palmas", cobertura: "ativo", fontes: ["Grupo Pax Palmas"] },
};

// Mapa em ladrilhos: [coluna, linha] aproximando a geografia do Brasil.
export const LADRILHOS: Record<string, [number, number]> = {
  RR: [2, 0], AP: [4, 0],
  AM: [1, 1], PA: [3, 1], MA: [4, 1], CE: [5, 1], RN: [6, 1],
  AC: [0, 2], RO: [1, 2], MT: [2, 2], TO: [3, 2], PI: [4, 2], PE: [5, 2], PB: [6, 2],
  MS: [2, 3], GO: [3, 3], DF: [4, 3], BA: [5, 3], AL: [6, 3],
  SP: [3, 4], MG: [4, 4], ES: [5, 4], SE: [6, 4],
  PR: [2, 5], RJ: [4, 5],
  SC: [2, 6],
  RS: [2, 7],
};

export const UFS = Object.keys(CAPITAIS).sort();
