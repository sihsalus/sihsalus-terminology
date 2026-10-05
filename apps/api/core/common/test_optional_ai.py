"""Regression checks for terminology servers without local model packages."""
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings

from core.common.exceptions import Http400
from core.common.search import CustomESSearch, Reranker
from core.common.utils import get_embeddings
from core.concepts.views import MetadataToConceptsListView, RerankConceptsListView


class OptionalAIConfigurationTest(SimpleTestCase):
    """Disabling semantic models must preserve ordinary terminology operations."""

    @override_settings(ENV='production', NO_LM=True)
    def test_disabled_embeddings_do_not_import_models(self):
        """Concept indexing can omit vectors without importing model libraries."""
        with patch.dict(sys.modules, {'sentence_transformers': None, 'torch': None}):
            self.assertIsNone(get_embeddings('rodilla'))
            self.assertEqual(CustomESSearch.get_search_string('Rodilla'), 'rodilla')

    @override_settings(NO_LM=True, NO_ENCODER=True)
    def test_disabled_reranker_refuses_custom_models(self):
        """A custom model request cannot bypass the deployment's resource limits."""
        with patch.dict(sys.modules, {'sentence_transformers': None, 'torch': None}):
            with self.assertRaises(Http400):
                Reranker(model_name='custom-model')

    @override_settings(NO_LM=True, NO_ENCODER=True)
    def test_semantic_endpoints_reject_before_processing(self):
        """Disabled operations return a client error before quota or worker use."""
        request = SimpleNamespace(data={'rows': [{'name': 'rodilla'}]}, query_params={'semantic': 'true'})
        with self.assertRaises(Http400):
            MetadataToConceptsListView().post(request)
        with self.assertRaises(Http400):
            RerankConceptsListView().post(request)

    @override_settings(ENV='production', NO_LM=False, LM_MODEL_NAME='model', LM=None)
    def test_enabled_embeddings_load_optional_model(self):
        """Full installations retain lazy model loading when it is requested."""
        model = Mock()
        model.encode.return_value = [0.1, 0.2]
        factory = Mock(return_value=model)
        with patch.dict(sys.modules, {'sentence_transformers': SimpleNamespace(SentenceTransformer=factory)}):
            self.assertEqual(get_embeddings('rodilla'), [0.1, 0.2])
        factory.assert_called_once_with('model')
        model.encode.assert_called_once_with('rodilla')
