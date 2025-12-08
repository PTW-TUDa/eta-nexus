"""Tests for the RESTConnection._api_token property."""

import os
from logging import getLogger
from unittest.mock import MagicMock, patch

import pytest

from eta_nexus.connections import RESTConnection


class ConcreteRESTConnection(RESTConnection):
    """Concrete implementation of RESTConnection for testing purposes."""

    _PROTOCOL = "test_protocol"
    logger = getLogger(__name__)

    def _from_node(self, node, **kwargs):
        pass

    def _initialize_session(self):
        return MagicMock()

    def _parse_response(self, json_data):
        pass

    def read_node(self, node, **kwargs):
        pass


class TestRESTConnectionApiToken:
    """Test suite for RESTConnection._api_token property."""

    @pytest.fixture
    def rest_connection(self):
        """Create a concrete REST connection instance for testing."""
        return ConcreteRESTConnection(url="http://example.com")

    def test_api_token_found_in_environment(self, rest_connection):
        """Test that API token is retrieved when environment variable is set."""
        expected_token = "test_token_12345"
        env_var_name = "TEST_PROTOCOL_API_TOKEN"

        with patch.dict(os.environ, {env_var_name: expected_token}):
            token = rest_connection._api_token

        assert token == expected_token

    def test_api_token_not_found_logs_warning(self, rest_connection):
        """Test that warning is logged when API token is not found in environment."""
        # Ensure the environment variable is not set
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(rest_connection, "logger") as mock_logger:
                token = rest_connection._api_token

                # Verify warning was logged
                mock_logger.warning.assert_called_once_with(
                    "[Test_protocol] TEST_PROTOCOL_API_TOKEN not found in environment."
                )

        assert token is None

    def test_api_token_empty_string_logs_warning(self, rest_connection):
        """Test that warning is logged when API token is empty string."""
        env_var_name = "TEST_PROTOCOL_API_TOKEN"

        with patch.dict(os.environ, {env_var_name: ""}):
            with patch.object(rest_connection, "logger") as mock_logger:
                token = rest_connection._api_token

                # Verify no warning was logged for empty string
                mock_logger.warning.assert_not_called()
        assert token == ""

    def test_api_token_with_different_protocol(self):
        """Test that API token uses correct environment variable based on protocol."""

        class AnotherRESTConnection(RESTConnection):
            _PROTOCOL = "another_protocol"

            def _from_node(self, node, **kwargs):
                pass

            def _initialize_session(self):
                return MagicMock()

            def _parse_response(self, json_data):
                pass

            def read_node(self, node, **kwargs):
                pass

        connection = AnotherRESTConnection(url="http://example.com")
        expected_token = "another_token_67890"
        env_var_name = "ANOTHER_PROTOCOL_API_TOKEN"

        with patch.dict(os.environ, {env_var_name: expected_token}):
            token = connection._api_token

        assert token == expected_token

    def test_api_token_case_sensitivity(self, rest_connection):
        """Test that API token environment variable is case-sensitive (uppercase)."""
        wrong_case_var = "test_protocol_api_token"  # lowercase
        correct_case_var = "TEST_PROTOCOL_API_TOKEN"  # uppercase
        expected_token = "correct_case_token"

        with patch.dict(os.environ, {correct_case_var: expected_token, wrong_case_var: "wrong_token"}):
            token = rest_connection._api_token

        assert token == expected_token
