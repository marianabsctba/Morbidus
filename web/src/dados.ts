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

// Só a situação de cada capital: quais fontes alimentam a base não vai para o código público.
export const CAPITAIS: Record<string, { capital: string; cobertura: Cobertura }> = {
  AC: { capital: "Rio Branco", cobertura: "sem_fonte" },
  AL: { capital: "Maceió", cobertura: "sem_fonte" },
  AP: { capital: "Macapá", cobertura: "sem_fonte" },
  AM: { capital: "Manaus", cobertura: "pendente" },
  BA: { capital: "Salvador", cobertura: "ativo" },
  CE: { capital: "Fortaleza", cobertura: "sem_fonte" },
  DF: { capital: "Brasília", cobertura: "ativo" },
  ES: { capital: "Vitória", cobertura: "pendente" },
  GO: { capital: "Goiânia", cobertura: "ativo" },
  MA: { capital: "São Luís", cobertura: "ativo" },
  MT: { capital: "Cuiabá", cobertura: "ativo" },
  MS: { capital: "Campo Grande", cobertura: "ativo" },
  MG: { capital: "Belo Horizonte", cobertura: "ativo" },
  PA: { capital: "Belém", cobertura: "sem_fonte" },
  PB: { capital: "João Pessoa", cobertura: "pendente" },
  PR: { capital: "Curitiba", cobertura: "ativo" },
  PE: { capital: "Recife", cobertura: "sem_fonte" },
  PI: { capital: "Teresina", cobertura: "ativo" },
  RJ: { capital: "Rio de Janeiro", cobertura: "sem_fonte" },
  RN: { capital: "Natal", cobertura: "ativo" },
  RS: { capital: "Porto Alegre", cobertura: "ativo" },
  RO: { capital: "Porto Velho", cobertura: "ativo" },
  RR: { capital: "Boa Vista", cobertura: "ativo" },
  SC: { capital: "Florianópolis", cobertura: "ativo" },
  SP: { capital: "São Paulo", cobertura: "ativo" },
  SE: { capital: "Aracaju", cobertura: "sem_fonte" },
  TO: { capital: "Palmas", cobertura: "ativo" },
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
