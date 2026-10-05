"""Public export links must use the TLS gateway, even with internal HTTP storage."""
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from core.services.storages.cloud.minio import MinIO


@override_settings(MINIO_ENDPOINT='storage:9000', MINIO_EXTERNAL_ENDPOINT='terminology.example.org',
                   MINIO_SECURE=False, MINIO_EXTERNAL_SECURE=True, MINIO_REGION='us-east-1',
                   MINIO_ACCESS_KEY='synthetic-access-key', MINIO_SECRET_KEY='synthetic-secret-key',
                   MINIO_BUCKET_NAME='terminology-exports')
class ExportGatewayTest(SimpleTestCase):
    """Signing must use the externally visible scheme and host."""

    @patch('core.services.storages.cloud.minio.Minio')
    def test_external_signer_uses_https(self, client):
        """Internal traffic and public signed links have independent TLS settings."""
        storage = MinIO()
        self.assertFalse(client.call_args_list[0].kwargs['secure'])
        self.assertTrue(client.call_args_list[1].kwargs['secure'])
        self.assertEqual(client.call_args_list[1].kwargs['endpoint'], 'terminology.example.org')
        storage.url_for('source/version/export.zip')
        client.return_value.get_presigned_url.assert_called_once_with(
            method='GET', bucket_name='terminology-exports', object_name='source/version/export.zip')
        self.assertEqual(storage.public_url_for('logo.png'),
                         'https://terminology.example.org/terminology-exports/logo.png')
