"""Guarda o HTML bruto de cada coleta para permitir reprocessar quando o parser melhorar."""

import io


class RawStore:
    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        raise NotImplementedError


class MemoryRawStore(RawStore):
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put(self, key: str, data: bytes, content_type: str = "text/html") -> None:
        self.objects[key] = data


class MinioRawStore(RawStore):
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
