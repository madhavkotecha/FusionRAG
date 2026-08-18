from __future__ import annotations

import io
import os

from minio import Minio


def get_minio_client() -> Minio:
    return Minio(
        endpoint=os.getenv("RRAG_MINIO_ENDPOINT", "minio:9000"),
        access_key=os.getenv("RRAG_MINIO_ACCESS_KEY", ""),
        secret_key=os.getenv("RRAG_MINIO_SECRET_KEY", ""),
        secure=os.getenv("RRAG_MINIO_USE_SSL", "false").lower() == "true",
    )


COMPONENTS_BUCKET = os.getenv("RRAG_MINIO_COMPONENTS_BUCKET", "components")


def ensure_bucket(client: Minio, bucket: str = COMPONENTS_BUCKET) -> None:
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)


def upload_component_file(
    client: Minio, workspace_id: str, filename: str, content: bytes
) -> str:
    object_path = f"{workspace_id}/{filename}"
    client.put_object(
        COMPONENTS_BUCKET,
        object_path,
        io.BytesIO(content),
        length=len(content),
        content_type="text/x-python",
    )
    return object_path


def download_component_file(client: Minio, object_path: str) -> bytes:
    response = client.get_object(COMPONENTS_BUCKET, object_path)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def delete_component_file(client: Minio, object_path: str) -> None:
    client.remove_object(COMPONENTS_BUCKET, object_path)
