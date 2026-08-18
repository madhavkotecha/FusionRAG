"""MinIO S3-compatible object storage service."""
from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from rrag_ingestion.config import settings

if TYPE_CHECKING:
    from minio import Minio

logger = logging.getLogger(__name__)

_client: Minio | None = None


def get_client() -> Minio:
    """Return a singleton MinIO client."""
    global _client
    if _client is None:
        from minio import Minio

        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl,
        )
    return _client


def ensure_bucket() -> None:
    """Create the configured bucket if it doesn't exist."""
    client = get_client()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
        logger.info(f"Created MinIO bucket: {settings.minio_bucket}")
    else:
        logger.debug(f"MinIO bucket already exists: {settings.minio_bucket}")


def make_object_key(workspace_id: str, doc_id: str, filename: str) -> str:
    """Build the S3 object key: {workspace}/{doc_id}/{filename}."""
    return f"{workspace_id}/{doc_id}/{filename}"


def upload_object(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Upload bytes to MinIO. Returns the object key."""
    client = get_client()
    client.put_object(
        settings.minio_bucket,
        key,
        io.BytesIO(data),
        length=len(data),
        content_type=content_type,
    )
    return key


def download_object(key: str) -> bytes:
    """Download an object from MinIO and return its bytes."""
    client = get_client()
    response = client.get_object(settings.minio_bucket, key)
    try:
        return response.read()
    finally:
        response.close()
        response.release_conn()


def download_to_file(key: str, local_path: str) -> str:
    """Download an object from MinIO to a local file path. Returns local_path."""
    import os

    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    client = get_client()
    client.fget_object(settings.minio_bucket, key, local_path)
    return local_path


def delete_object(key: str) -> None:
    """Delete an object from MinIO."""
    client = get_client()
    client.remove_object(settings.minio_bucket, key)


def get_presigned_url(key: str, expires_seconds: int = 3600) -> str:
    """Generate a presigned GET URL for the object."""
    from datetime import timedelta

    client = get_client()
    return client.presigned_get_object(
        settings.minio_bucket,
        key,
        expires=timedelta(seconds=expires_seconds),
    )


def object_exists(key: str) -> bool:
    """Check if an object exists in MinIO."""
    client = get_client()
    try:
        client.stat_object(settings.minio_bucket, key)
        return True
    except Exception:
        return False
