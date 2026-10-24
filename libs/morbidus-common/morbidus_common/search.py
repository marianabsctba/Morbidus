"""Índice de busca de registros de óbito: OpenSearch em produção, memória em testes."""

from morbidus_common.events import DeathRecordNormalized
from morbidus_common.text import name_similarity, normalize_name, phonetic_key

_EVENT_FIELDS = {"event_id", "occurred_at", "schema_version"}


def _as_doc(record: DeathRecordNormalized) -> dict:
    return record.model_dump(mode="json", exclude=_EVENT_FIELDS)


class DeathIndex:
    def ensure_index(self) -> None:
        pass

    def upsert(self, record: DeathRecordNormalized) -> None:
        raise NotImplementedError

    def search(self, nome: str, uf: str | None = None, limit: int = 10) -> list[dict]:
        raise NotImplementedError


class InMemoryDeathIndex(DeathIndex):
    def __init__(self, min_similarity: float = 0.6) -> None:
        self.docs: dict[str, dict] = {}
        self._min_similarity = min_similarity

    def upsert(self, record: DeathRecordNormalized) -> None:
        self.docs[record.record_id] = _as_doc(record)

    def search(self, nome: str, uf: str | None = None, limit: int = 10) -> list[dict]:
        chave = phonetic_key(nome)
        hits = []
        for doc in self.docs.values():
            if uf and doc["uf"] != uf.upper():
                continue
            sim = name_similarity(nome, doc["nome"])
            if sim >= self._min_similarity or doc["chave_fonetica"] == chave:
                hits.append((sim, doc))
        hits.sort(key=lambda h: h[0], reverse=True)
        return [doc for _, doc in hits[:limit]]


class OpenSearchDeathIndex(DeathIndex):
    INDEX = "death-records"
    MAPPINGS = {
        "properties": {
            "record_id": {"type": "keyword"},
            "nome": {"type": "text"},
            "nome_normalizado": {"type": "text"},
            "chave_fonetica": {"type": "keyword"},
            "idade": {"type": "integer"},
            "data_nascimento": {"type": "date"},
            "data_falecimento": {"type": "date"},
            "ano_nascimento_estimado": {"type": "integer"},
            "cidade": {"type": "keyword"},
            "uf": {"type": "keyword"},
            "fontes": {"type": "keyword"},
            "canario": {"type": "boolean"},
        }
    }

    def __init__(self, url: str) -> None:
        from opensearchpy import OpenSearch

        self._client = OpenSearch(hosts=[url])

    def ensure_index(self) -> None:
        if not self._client.indices.exists(index=self.INDEX):
            self._client.indices.create(index=self.INDEX, body={"mappings": self.MAPPINGS})

    def upsert(self, record: DeathRecordNormalized) -> None:
        self._client.index(index=self.INDEX, id=record.record_id, body=_as_doc(record))

    def search(self, nome: str, uf: str | None = None, limit: int = 10) -> list[dict]:
        query: dict = {
            "bool": {
                "should": [
                    {
                        "match": {
                            "nome_normalizado": {
                                "query": normalize_name(nome),
                                "fuzziness": "AUTO",
                                "minimum_should_match": "2<75%",
                            }
                        }
                    },
                    {"term": {"chave_fonetica": phonetic_key(nome)}},
                ],
                "minimum_should_match": 1,
            }
        }
        if uf:
            query["bool"]["filter"] = [{"term": {"uf": uf.upper()}}]
        res = self._client.search(index=self.INDEX, body={"query": query, "size": limit})
        return [hit["_source"] for hit in res["hits"]["hits"]]


def make_index(backend: str, opensearch_url: str) -> DeathIndex:
    if backend == "opensearch":
        return OpenSearchDeathIndex(opensearch_url)
    return InMemoryDeathIndex()
