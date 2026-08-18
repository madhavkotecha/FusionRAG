"""Tests for MinIO object store service (all calls mocked)."""
from __future__ import annotations

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

# Patch settings before import so the module picks up test values
_SETTINGS_PATCH = {
    "minio_endpoint": "localhost:9000",
    "minio_access_key": "testaccesskey",
    "minio_secret_key": "testsecretkey",
    "minio_bucket": "test-bucket",
    "minio_use_ssl": False,
}


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the module-level singleton between tests."""
    from rrag_ingestion.services import object_store
    object_store._client = None
    yield
    object_store._client = None


@pytest.fixture
def mock_minio():
    """Provide a mocked Minio client and patch the constructor."""
    mock_client = MagicMock()
    with patch("rrag_ingestion.services.object_store.settings") as mock_settings:
        for k, v in _SETTINGS_PATCH.items():
            setattr(mock_settings, k, v)
        with patch("minio.Minio", return_value=mock_client) as mock_cls:
            yield mock_client, mock_cls


class TestGetClient:
    def test_creates_singleton(self, mock_minio):
        mock_client, mock_cls = mock_minio
        from rrag_ingestion.services import object_store

        client1 = object_store.get_client()
        client2 = object_store.get_client()
        assert client1 is client2
        mock_cls.assert_called_once()

    def test_uses_settings(self, mock_minio):
        mock_client, mock_cls = mock_minio
        from rrag_ingestion.services import object_store

        object_store.get_client()
        mock_cls.assert_called_once_with(
            "localhost:9000",
            access_key="testaccesskey",
            secret_key="testsecretkey",
            secure=False,
        )


class TestEnsureBucket:
    def test_creates_bucket_when_missing(self, mock_minio):
        mock_client, _ = mock_minio
        mock_client.bucket_exists.return_value = False
        from rrag_ingestion.services import object_store

        object_store.ensure_bucket()
        mock_client.make_bucket.assert_called_once_with("test-bucket")

    def test_skips_when_exists(self, mock_minio):
        mock_client, _ = mock_minio
        mock_client.bucket_exists.return_value = True
        from rrag_ingestion.services import object_store

        object_store.ensure_bucket()
        mock_client.make_bucket.assert_not_called()


class TestMakeObjectKey:
    def test_builds_key(self):
        from rrag_ingestion.services.object_store import make_object_key

        key = make_object_key("ws-1", "doc-abc", "paper.pdf")
        assert key == "ws-1/doc-abc/paper.pdf"


class TestUploadObject:
    def test_upload_calls_put_object(self, mock_minio):
        mock_client, _ = mock_minio
        from rrag_ingestion.services import object_store

        result = object_store.upload_object("ws/doc/file.pdf", b"hello", "application/pdf")
        assert result == "ws/doc/file.pdf"
        mock_client.put_object.assert_called_once()
        args, kwargs = mock_client.put_object.call_args
        assert args[0] == "test-bucket"
        assert args[1] == "ws/doc/file.pdf"
        assert kwargs["length"] == 5
        assert kwargs["content_type"] == "application/pdf"


class TestDownloadObject:
    def test_download_returns_bytes(self, mock_minio):
        mock_client, _ = mock_minio
        mock_response = MagicMock()
        mock_response.read.return_value = b"file content"
        mock_client.get_object.return_value = mock_response
        from rrag_ingestion.services import object_store

        data = object_store.download_object("ws/doc/file.pdf")
        assert data == b"file content"
        mock_response.close.assert_called_once()
        mock_response.release_conn.assert_called_once()


class TestDownloadToFile:
    def test_download_to_file(self, mock_minio):
        mock_client, _ = mock_minio
        from rrag_ingestion.services import object_store

        result = object_store.download_to_file("ws/doc/file.pdf", "/tmp/test/file.pdf")
        assert result == "/tmp/test/file.pdf"
        mock_client.fget_object.assert_called_once_with("test-bucket", "ws/doc/file.pdf", "/tmp/test/file.pdf")


class TestDeleteObject:
    def test_delete(self, mock_minio):
        mock_client, _ = mock_minio
        from rrag_ingestion.services import object_store

        object_store.delete_object("ws/doc/file.pdf")
        mock_client.remove_object.assert_called_once_with("test-bucket", "ws/doc/file.pdf")


class TestObjectExists:
    def test_returns_true(self, mock_minio):
        mock_client, _ = mock_minio
        mock_client.stat_object.return_value = MagicMock()
        from rrag_ingestion.services import object_store

        assert object_store.object_exists("ws/doc/file.pdf") is True

    def test_returns_false_on_error(self, mock_minio):
        mock_client, _ = mock_minio
        mock_client.stat_object.side_effect = Exception("Not found")
        from rrag_ingestion.services import object_store

        assert object_store.object_exists("ws/doc/file.pdf") is False


class TestGetPresignedUrl:
    def test_returns_url(self, mock_minio):
        mock_client, _ = mock_minio
        mock_client.presigned_get_object.return_value = "https://minio:9000/test-bucket/ws/doc/file.pdf?sig=abc"
        from rrag_ingestion.services import object_store

        url = object_store.get_presigned_url("ws/doc/file.pdf", expires_seconds=600)
        assert "minio" in url
        mock_client.presigned_get_object.assert_called_once()
