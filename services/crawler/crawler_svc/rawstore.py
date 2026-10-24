"""Guarda o HTML bruto de cada coleta para permitir reprocessar quando o parser melhorar."""

import io
import time
from pathlib import Path


class RawStore:
    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        raise NotImplementedError

    def purge(self, older_than_days: int) -> int:
        """Apaga páginas antigas. O HTML bruto traz dados de terceiros (parentes,
        endereços) e só serve para reprocessar, então não deve ficar para sempre."""
        return 0


class MemoryRawStore(RawStore):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        self.objects[key] = data


class FileRawStore(RawStore):
    """Grava em disco (um volume Docker em produção). Suficiente para um servidor só."""

    def __init__(self, base_dir: str) -> None:
        self._base = Path(base_dir).resolve()

    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        destino = (self._base / key).resolve()
        if self._base not in destino.parents:
            raise ValueError(f"chave fora do diretório base: {key}")
        if destino.exists():
            return  # A chave carrega o hash do conteúdo: mesmo nome, mesmo arquivo.
        destino.parent.mkdir(parents=True, exist_ok=True)
        tmp = destino.with_suffix(destino.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(destino)

    def purge(self, older_than_days: int) -> int:
        limite = time.time() - older_than_days * 86400
        apagados = 0
        for arquivo in self._base.rglob("*"):
            if arquivo.is_file() and arquivo.stat().st_mtime < limite:
                arquivo.unlink()
                apagados += 1
        for pasta in sorted((p for p in self._base.rglob("*") if p.is_dir()), reverse=True):
            if not any(pasta.iterdir()):
                pasta.rmdir()
        return apagados


class MinioRawStore(RawStore):
    """Qualquer serviço compatível com S3 (AWS, Cloudflare R2, Garage, MinIO)."""

    def __init__(self, endpoint: str, access_key: str, secret_key: str, bucket: str, secure: bool) -> None:
        from minio import Minio

        self._client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
        self._bucket = bucket
        self._bucket_ready = False

    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        if not self._bucket_ready:
            if not self._client.bucket_exists(self._bucket):
                self._client.make_bucket(self._bucket)
            self._bucket_ready = True
        self._client.put_object(self._bucket, key, io.BytesIO(data), len(data), content_type=content_type)
