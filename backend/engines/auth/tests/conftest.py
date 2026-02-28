from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def mock_transaction_on_commit():
    """Execute on_commit callbacks immediately in tests."""
    with patch("django.db.transaction.on_commit", side_effect=lambda f: f()):
        yield
