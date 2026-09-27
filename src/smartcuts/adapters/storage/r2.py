"""Cloudflare R2 (API compatible con S3).

Sin coste de salida de datos: los usuarios descargan sus clips directamente
de R2 con URLs firmadas, sin pasar por la API. Con `jurisdiction="eu"` se usa
el endpoint de la UE (el bucket debe crearse con jurisdicción EU).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any
from urllib.parse import quote

from smartcuts.domain.errors import ConfigurationError
from smartcuts.domain.ports import UploadedPart
from smartcuts.infra.registry import register


@register("storage", "r2")
class R2Storage:
    name = "r2"

    def __init__(
        self,
        account_id: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str,
        jurisdiction: str = "eu",
        **_: Any,
    ) -> None:
        if not all([account_id, access_key_id, secret_access_key, bucket]):
            raise ConfigurationError("Faltan credenciales de R2 (SMARTCUTS_STORAGE__R2_*)")
        import boto3
        from botocore.config import Config

        host = f"{account_id}.eu.r2.cloudflarestorage.com" if jurisdiction == "eu" else (
            f"{account_id}.r2.cloudflarestorage.com"
        )
        self.bucket = bucket
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{host}",
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
        )

    def put_file(self, key: str, path: Path, content_type: str) -> None:
        self.s3.upload_file(str(path), self.bucket, key, ExtraArgs={"ContentType": content_type})

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def read_bytes(self, key: str) -> bytes | None:
        from botocore.exceptions import ClientError

        try:
            return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("NoSuchKey", "404"):
                return None
            raise

    def iter_bytes(self, key: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        body = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
        try:
            yield from body.iter_chunks(chunk_size)
        finally:
            body.close()

    def download_to(self, key: str, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.s3.download_file(self.bucket, key, str(dest))
        return dest

    def size(self, key: str) -> int | None:
        from botocore.exceptions import ClientError

        try:
            return int(self.s3.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def delete_prefix(self, prefix: str) -> int:
        deleted = 0
        paginator = self.s3.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            objects = [{"Key": o["Key"]} for o in page.get("Contents", [])]
            if objects:
                self.s3.delete_objects(Bucket=self.bucket, Delete={"Objects": objects, "Quiet": True})
                deleted += len(objects)
        return deleted

    def signed_url(self, key: str, *, expires: int = 3600, download_name: str | None = None) -> str:
        params: dict[str, Any] = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f"attachment; filename*=UTF-8''{quote(download_name)}"
        return self.s3.generate_presigned_url("get_object", Params=params, ExpiresIn=expires)

    def local_path(self, key: str) -> Path | None:
        return None

    # --- subida multiparte (el navegador sube cada parte directamente a R2) ---------------

    def create_multipart(self, key: str, content_type: str) -> str:
        return self.s3.create_multipart_upload(Bucket=self.bucket, Key=key, ContentType=content_type)["UploadId"]

    def presign_part(self, key: str, upload_id: str, part_number: int, *, max_bytes: int, expires: int = 3600) -> str:
        # R2 no admite límite de tamaño en URLs firmadas: el total se verifica al completar.
        return self.s3.generate_presigned_url(
            "upload_part",
            Params={"Bucket": self.bucket, "Key": key, "UploadId": upload_id, "PartNumber": part_number},
            ExpiresIn=expires,
        )

    def list_parts(self, key: str, upload_id: str) -> list[UploadedPart]:
        parts: list[UploadedPart] = []
        paginator = self.s3.get_paginator("list_parts")
        for page in paginator.paginate(Bucket=self.bucket, Key=key, UploadId=upload_id):
            parts += [UploadedPart(p["PartNumber"], p["ETag"], int(p["Size"])) for p in page.get("Parts", [])]
        return parts

    def complete_multipart(self, key: str, upload_id: str, parts: list[UploadedPart]) -> None:
        self.s3.complete_multipart_upload(
            Bucket=self.bucket,
            Key=key,
            UploadId=upload_id,
            MultipartUpload={"Parts": [{"PartNumber": p.part_number, "ETag": p.etag} for p in parts]},
        )

    def abort_multipart(self, key: str, upload_id: str) -> None:
        from botocore.exceptions import ClientError

        try:
            self.s3.abort_multipart_upload(Bucket=self.bucket, Key=key, UploadId=upload_id)
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") not in ("NoSuchUpload", "404"):
                raise
