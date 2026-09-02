"""
Telemetry Engine — read beacon tests.

The endpoint under test is the project's only UNAUTHENTICATED WRITE surface,
so these tests are as much about what it refuses as what it records.
"""

from django.core.cache import cache

from rest_framework import status
from rest_framework.test import APIClient

import pytest

from engines.auth.models import User
from engines.telemetry.models import ContentRead, VisitLog

BEACON_URL = "/api/v1/telemetry/read/"

VALID_PAYLOAD = {
    "content_type": ContentRead.CONTENT_TYPE_DAILY_CA,
    "content_id": "some-daily-ca-slug",
}


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """The limiter is cache-backed; a leftover counter would leak between tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def telemetry_on(monkeypatch):
    """
    Switch telemetry on.

    Config is read from the environment at call time, not cached at import, so
    monkeypatching here is enough — no reload, no settings override.
    """
    monkeypatch.setenv("TELEMETRY_ENABLED", "true")
    monkeypatch.setenv("TELEMETRY_IP_SALT", "obviously-fake-test-salt")


@pytest.fixture
def api_client():
    return APIClient()


@pytest.mark.django_db
class TestBeaconAccess:
    """Who is allowed to post at all."""

    def test_anonymous_post_is_accepted(self, api_client, telemetry_on):
        """
        REGRESSION GUARD (scan finding F-A).

        DRF's project default is IsAuthenticatedOrReadOnly. Without an explicit
        permission_classes = [AllowAny] on the view, this POST returns 403 for
        every anonymous reader while continuing to work for a signed-in
        developer — so the table fills with authenticated traffic only, looks
        plausible, and is systematically wrong.

        If this test ever fails with 403, that line has been removed.
        """
        response = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 1

    def test_anonymous_row_is_marked_unauthenticated(self, api_client, telemetry_on):
        api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        assert ContentRead.objects.get().is_authenticated is False

    def test_authenticated_row_is_marked_authenticated(self, api_client, telemetry_on):
        user = User.objects.create_user(email="reader@example.com", password="pass")
        api_client.force_authenticate(user=user)

        api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        row = ContentRead.objects.get()
        assert row.is_authenticated is True
        # The model carries no user FK — only the boolean. Guard against anyone
        # "helpfully" adding one later.
        assert not hasattr(row, "user")


@pytest.mark.django_db
class TestBeaconDedupe:
    """One row per reader, per item, per day — enforced by the database."""

    def test_repeat_read_same_day_creates_only_one_row(self, api_client, telemetry_on):
        first = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")
        second = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        # The duplicate is a SUCCESS, not an error: a refresh must neither
        # inflate the count nor look like a failure to the page.
        assert first.status_code == status.HTTP_204_NO_CONTENT
        assert second.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 1

    def test_duplicate_does_not_poison_the_transaction(self, api_client, telemetry_on):
        """
        The IntegrityError is caught inside transaction.atomic().

        Without that savepoint the connection would be left needing rollback and
        the NEXT write would fail with "current transaction is aborted". This
        asserts a different article still records after a duplicate.
        """
        api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")
        api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        response = api_client.post(
            BEACON_URL,
            {**VALID_PAYLOAD, "content_id": "a-different-slug"},
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 2

    def test_different_readers_each_get_a_row(self, api_client, telemetry_on):
        api_client.post(
            BEACON_URL, VALID_PAYLOAD, format="json", HTTP_X_FORWARDED_FOR="203.0.113.1"
        )
        api_client.post(
            BEACON_URL, VALID_PAYLOAD, format="json", HTTP_X_FORWARDED_FOR="203.0.113.2"
        )

        assert ContentRead.objects.count() == 2


@pytest.mark.django_db
class TestBeaconIdentity:
    """Identity is derived server-side, and never stored raw."""

    def test_visitor_identity_comes_from_x_forwarded_for(
        self, api_client, telemetry_on
    ):
        """
        REGRESSION GUARD (scan finding F-I).

        Render sits behind a load balancer, so REMOTE_ADDR is the PROXY. The
        test client sends the same REMOTE_ADDR (127.0.0.1) for both requests
        below — so if the code read REMOTE_ADDR the two hashes would be
        IDENTICAL and only one row would survive the unique constraint.

        Two rows means the forwarded header was honoured.
        """
        api_client.post(
            BEACON_URL,
            VALID_PAYLOAD,
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.7",
        )
        api_client.post(
            BEACON_URL,
            VALID_PAYLOAD,
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.8",
        )

        hashes = set(ContentRead.objects.values_list("ip_hash", flat=True))
        assert len(hashes) == 2

    def test_same_visitor_hashes_consistently(self, api_client, telemetry_on):
        api_client.post(
            BEACON_URL,
            VALID_PAYLOAD,
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.7",
        )
        api_client.post(
            BEACON_URL,
            {**VALID_PAYLOAD, "content_id": "another-slug"},
            format="json",
            HTTP_X_FORWARDED_FOR="198.51.100.7",
        )

        hashes = set(ContentRead.objects.values_list("ip_hash", flat=True))
        assert len(hashes) == 1

    def test_raw_ip_is_never_stored(self, api_client, telemetry_on):
        raw_ip = "198.51.100.42"
        api_client.post(
            BEACON_URL, VALID_PAYLOAD, format="json", HTTP_X_FORWARDED_FOR=raw_ip
        )

        stored = ContentRead.objects.get().ip_hash
        assert raw_ip not in stored
        assert len(stored) == 64  # SHA-256 hex digest


@pytest.mark.django_db
class TestBeaconKillSwitch:
    """Nothing is recorded unless telemetry is explicitly and safely enabled."""

    def test_disabled_records_nothing_but_still_succeeds(self, api_client, monkeypatch):
        monkeypatch.setenv("TELEMETRY_ENABLED", "false")

        response = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        # 204, not an error: whether telemetry runs is not the caller's concern.
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 0

    def test_missing_salt_disables_collection(self, api_client, monkeypatch):
        """
        FAIL SAFE, not fail open.

        An unsalted SHA-256 of an IPv4 address is reversible by enumerating the
        address space in seconds. A forgotten env var must stop collection, not
        quietly produce data that only looks pseudonymous.
        """
        monkeypatch.setenv("TELEMETRY_ENABLED", "true")
        monkeypatch.delenv("TELEMETRY_IP_SALT", raising=False)

        response = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 0


@pytest.mark.django_db
class TestBeaconValidation:
    """Hostile input stops at the serializer."""

    def test_unknown_content_type_is_rejected(self, api_client, telemetry_on):
        response = api_client.post(
            BEACON_URL,
            {"content_type": "not_a_real_type", "content_id": "x"},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ContentRead.objects.count() == 0

    @pytest.mark.parametrize(
        "bad_id",
        [
            "has spaces",
            "semi;colon",
            "<script>alert(1)</script>",
            "slash/es",
            "",
        ],
    )
    def test_malformed_content_id_is_rejected(self, api_client, telemetry_on, bad_id):
        response = api_client.post(
            BEACON_URL,
            {**VALID_PAYLOAD, "content_id": bad_id},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert ContentRead.objects.count() == 0

    def test_overlong_content_id_is_rejected(self, api_client, telemetry_on):
        response = api_client.post(
            BEACON_URL,
            {**VALID_PAYLOAD, "content_id": "a" * 300},
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_client_cannot_set_server_derived_fields(self, api_client, telemetry_on):
        """
        The serializer accepts two fields. Anything else is ignored, not honoured.

        A caller able to set ip_hash could send a different value every time and
        defeat the unique constraint that caps this table's growth.
        """
        response = api_client.post(
            BEACON_URL,
            {
                **VALID_PAYLOAD,
                "ip_hash": "f" * 64,
                "is_authenticated": True,
                "read_date": "2020-01-01",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        row = ContentRead.objects.get()
        assert row.ip_hash != "f" * 64
        assert row.is_authenticated is False
        assert row.read_date.year != 2020


@pytest.mark.django_db
class TestBeaconRateLimit:
    """The public write surface is throttled, but never at the cost of uptime."""

    def test_requests_beyond_the_limit_are_rejected(
        self, api_client, telemetry_on, monkeypatch
    ):
        monkeypatch.setenv("TELEMETRY_BEACON_RATE_LIMIT", "2")

        # Distinct ids so the daily dedupe cannot mask the limiter's effect.
        for slug in ("one", "two"):
            response = api_client.post(
                BEACON_URL, {**VALID_PAYLOAD, "content_id": slug}, format="json"
            )
            assert response.status_code == status.HTTP_204_NO_CONTENT

        blocked = api_client.post(
            BEACON_URL, {**VALID_PAYLOAD, "content_id": "three"}, format="json"
        )

        assert blocked.status_code == status.HTTP_429_TOO_MANY_REQUESTS
        assert ContentRead.objects.count() == 2

    def test_limiter_fails_open_when_cache_is_down(
        self, api_client, telemetry_on, monkeypatch
    ):
        """
        A limiter outage must not become a site outage.

        Mirrors the documented behaviour of research_agent's Redis limiter.
        """

        def explode(*args, **kwargs):
            raise ConnectionError("redis is down")

        monkeypatch.setattr("engines.telemetry.utils.cache.add", explode)

        response = api_client.post(BEACON_URL, VALID_PAYLOAD, format="json")

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert ContentRead.objects.count() == 1


@pytest.mark.django_db
class TestBeaconIsNotSelfLogging:
    """The beacon must not appear in its own traffic log."""

    def test_beacon_request_creates_no_visit_log_row(self, api_client, telemetry_on):
        """
        /api/v1/telemetry/ is in the middleware's SKIP_PATH_PREFIXES. Without
        that, every read would be recorded twice — once as content, and once as
        traffic about recording content.
        """
        api_client.post(
            BEACON_URL, VALID_PAYLOAD, format="json", HTTP_SEC_FETCH_MODE="cors"
        )

        assert ContentRead.objects.count() == 1
        assert VisitLog.objects.count() == 0
