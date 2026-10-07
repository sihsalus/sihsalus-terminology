"""Signed download discovery must retain export permissions and legacy responses."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.http import Http404
from django.test import SimpleTestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIRequestFactory, force_authenticate

from core.collections.views import CollectionVersionExportView, CollectionVersionExternalExportView
from core.sources.views import SourceVersionExportView, SourceVersionExternalExportView


class ExportDownloadTest(SimpleTestCase):
    """Check both repository kinds without contacting storage or a database."""

    export_views = (SourceVersionExportView, CollectionVersionExportView)
    external_views = (SourceVersionExternalExportView, CollectionVersionExternalExportView)
    signed_url = 'https://storage.example.org/export.zip?signature=synthetic'

    def make_view(self, view_type, query=None):
        """Use each real view's object lookup and permission boundary."""
        view = view_type()
        version = Mock(is_head=False, is_exporting=False)
        version.has_export.return_value = True
        version.get_export_path.return_value = 'synthetic/export.zip'
        version.external_exports.filter.return_value.first.return_value = SimpleNamespace(
            file_url=self.signed_url)
        request = SimpleNamespace(query_params=query or {}, user=Mock(
            is_staff=False, is_superuser=False, is_admin_for=Mock(return_value=False)))
        view.request = request
        view.kwargs = {'version': 'published', 'external_export_key': 'synthetic'}
        view.get_queryset = Mock(return_value=Mock(first=Mock(return_value=version)))
        view.check_object_permissions = Mock()
        return view, version, request

    @patch('core.common.mixins.get_export_service')
    def test_opt_in_returns_the_signed_url_for_sources_and_collections(self, storage):
        """Only accepted truthy values select JSON instead of the legacy redirect."""
        storage.return_value.url_for.return_value = self.signed_url
        for view_type in self.export_views:
            for value in ('true', 'True', '1'):
                with self.subTest(view=view_type.__name__, value=value):
                    view, version, request = self.make_view(view_type, {'noRedirect': value})
                    response = view.get(request)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, {'url': self.signed_url})
                    view.check_object_permissions.assert_called_once_with(request, version)

    @patch('core.common.mixins.get_export_service')
    def test_legacy_redirect_remains_the_default(self, storage):
        """Existing callers retain HTTP 302 unless they explicitly opt in."""
        storage.return_value.url_for.return_value = self.signed_url
        for view_type in self.export_views:
            for query in ({}, {'noRedirect': 'false'}, {'noRedirect': '0'}):
                with self.subTest(view=view_type.__name__, query=query):
                    view, _, request = self.make_view(view_type, query)
                    response = view.get(request)
                    self.assertEqual(response.status_code, 302)
                    self.assertEqual(response['Location'], self.signed_url)

    @patch('core.common.mixins.get_export_service')
    def test_permissions_run_before_export_discovery(self, storage):
        """A denied repository never produces a signed URL or reads external exports."""
        for view_type in self.export_views + self.external_views:
            with self.subTest(view=view_type.__name__):
                view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                view.check_object_permissions.side_effect = PermissionDenied
                with self.assertRaises(PermissionDenied):
                    view.get(request)
                version.has_export.assert_not_called()
                version.external_exports.filter.assert_not_called()
        storage.assert_not_called()

    @patch('core.common.mixins.get_export_service')
    def test_anonymous_requests_are_refused_before_object_lookup(self, storage):
        """The new query parameter does not bypass existing authentication."""
        factory = APIRequestFactory()
        for view_type in self.export_views + self.external_views:
            with self.subTest(view=view_type.__name__):
                request = factory.get('/synthetic/export/', {'noRedirect': 'true'})
                force_authenticate(request, user=AnonymousUser())
                with patch.object(view_type, 'get_queryset') as queryset:
                    response = view_type.as_view()(request, version='published')
                    self.assertIn(response.status_code, (401, 403))
                    queryset.assert_not_called()
        storage.assert_not_called()

    @patch('core.common.mixins.get_export_service')
    def test_missing_repository_stays_404(self, storage):
        """No signed URL is produced when the permitted object does not exist."""
        for view_type in self.export_views + self.external_views:
            with self.subTest(view=view_type.__name__):
                view, _, request = self.make_view(view_type, {'noRedirect': 'true'})
                view.get_queryset.return_value.first.return_value = None
                with self.assertRaises(Http404):
                    view.get(request)
        storage.assert_not_called()

    @patch('core.common.mixins.get_export_service')
    def test_missing_and_processing_exports_keep_their_status(self, storage):
        """Discovery returns 204 or 208 without trying to sign an unavailable export."""
        for view_type in self.export_views:
            for processing, expected in ((False, 204), (True, 208)):
                with self.subTest(view=view_type.__name__, processing=processing):
                    view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                    version.is_exporting = processing
                    version.has_export.return_value = False
                    self.assertEqual(view.get(request).status_code, expected)
        storage.assert_not_called()

    @patch('core.common.mixins.get_export_service')
    def test_head_export_still_requires_repository_admin(self, storage):
        """Ordinary repository readers cannot request an unreleased HEAD export."""
        for view_type in self.export_views:
            with self.subTest(view=view_type.__name__):
                view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                version.is_head = True
                self.assertEqual(view.get(request).status_code, 405)
                version.has_export.assert_not_called()
        storage.assert_not_called()

    @patch('core.common.mixins.get_export_service')
    def test_head_repository_admin_can_discover_a_download(self, storage):
        """The supported HEAD export permission remains available to repository admins."""
        storage.return_value.url_for.return_value = self.signed_url
        for view_type in self.export_views:
            with self.subTest(view=view_type.__name__):
                view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                version.is_head = True
                request.user.is_admin_for.return_value = True
                self.assertEqual(view.get(request).data, {'url': self.signed_url})

    @patch('core.common.mixins.get_export_service')
    def test_failed_signing_remains_an_error(self, storage):
        """A missing storage URL never becomes a successful JSON response."""
        storage.return_value.url_for.return_value = None
        for view_type in self.export_views:
            with self.subTest(view=view_type.__name__):
                view, _, request = self.make_view(view_type, {'noRedirect': 'true'})
                self.assertEqual(view.get(request).status_code, 500)

    def test_external_exports_share_the_opt_in_contract(self):
        """External files support JSON discovery while preserving their redirect."""
        for view_type in self.external_views:
            for query, expected in (({'noRedirect': 'true'}, 200), ({}, 302),
                                    ({'noRedirect': 'false'}, 302)):
                with self.subTest(view=view_type.__name__, query=query):
                    view, _, request = self.make_view(view_type, query)
                    response = view.get(request)
                    self.assertEqual(response.status_code, expected)
                    if expected == 200:
                        self.assertEqual(response.data, {'url': self.signed_url})
                    else:
                        self.assertEqual(response['Location'], self.signed_url)

    def test_external_export_missing_url_remains_an_error(self):
        """External metadata without a signed URL cannot report download success."""
        for view_type in self.external_views:
            with self.subTest(view=view_type.__name__):
                view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                version.external_exports.filter.return_value.first.return_value = SimpleNamespace(file_url=None)
                self.assertEqual(view.get(request).status_code, 500)

    def test_missing_external_export_stays_404(self):
        """Opting in does not invent a download for an unknown external export."""
        for view_type in self.external_views:
            with self.subTest(view=view_type.__name__):
                view, version, request = self.make_view(view_type, {'noRedirect': 'true'})
                version.external_exports.filter.return_value.first.return_value = None
                with self.assertRaises(Http404):
                    view.get(request)
