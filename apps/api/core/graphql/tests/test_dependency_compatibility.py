"""Check the deployed GraphQL dependency combination without external services."""
import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from asgiref.sync import async_to_sync
from django.test import SimpleTestCase
from strawberry.exceptions import PermissionReturnedAwaitableInSyncContextError
from strawberry.permission import BasePermission, PermissionExtension

from core.graphql.schema import schema


class GraphQLDependencyCompatibilityTest(SimpleTestCase):
    """Keep schema execution and permission checks compatible with security updates."""

    def test_schema_and_optimizer_execute(self):
        """The real schema and Django optimizer must initialize and execute together."""
        result = async_to_sync(schema.execute)('{ __typename __schema { queryType { name } } }')
        self.assertIsNone(result.errors)
        self.assertEqual(result.data['__typename'], 'Query')
        self.assertEqual(result.data['__schema']['queryType']['name'], 'Query')

    def test_authentication_and_required_arguments_remain_enforced(self):
        """The real resolver must reject invalid requests before any database lookup."""
        for auth_status, expected in (
                ('none', 'Authentication required'), ('invalid', 'Authentication failure'),
                ('valid', 'Either conceptIds or query must be provided.')):
            with self.subTest(auth_status=auth_status), self.assertLogs('strawberry.execution', level='ERROR'):
                result = async_to_sync(schema.execute)(
                    '{ concepts { totalCount } }', context_value=SimpleNamespace(auth_status=auth_status))
                self.assertEqual([error.message for error in result.errors], [expected])

    def test_sync_permission_returning_awaitable_fails_closed(self):
        """A coroutine is not a true permission result and cannot reach the resolver."""
        permission = Mock(spec=BasePermission)
        permission.has_permission.return_value = asyncio.sleep(0, result=False)
        resolver = Mock()
        extension = PermissionExtension(permissions=[permission])
        with self.assertRaises(PermissionReturnedAwaitableInSyncContextError):
            extension.resolve(resolver, None, None)
        resolver.assert_not_called()
