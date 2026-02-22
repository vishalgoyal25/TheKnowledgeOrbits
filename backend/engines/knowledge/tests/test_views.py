"""Knowledge Engine - View Tests"""

import pytest
from rest_framework.test import APIClient
from rest_framework import status
from engines.knowledge.models import Program, Subject, Module, Topic
from engines.auth.models import User


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    user = User.objects.create_user(email="test@test.com", password="pass")
    user.is_verified = True
    user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, user):
    api_client.force_authenticate(user=user)
    return api_client, user


@pytest.mark.django_db
class TestProgramViewSet:
    def test_list_programs(self, api_client):
        Program.objects.create(name="UPSC CSE")
        Program.objects.create(name="State PSC")

        response = api_client.get("/api/v1/knowledge/programs/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2


@pytest.mark.django_db
class TestTopicViewSet:
    def test_list_topics(self, api_client):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        Topic.objects.create(name="Article 370", module=module, subject=subject)
        Topic.objects.create(name="Article 371", module=module, subject=subject)

        response = api_client.get("/api/v1/knowledge/topics/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_filter_topics_by_difficulty(self, api_client):
        program = Program.objects.create(name="UPSC CSE")
        subject = Subject.objects.create(name="Polity", program=program)
        module = Module.objects.create(name="Constitution", subject=subject)

        Topic.objects.create(
            name="Easy Topic", module=module, subject=subject, difficulty_level="easy"
        )
        Topic.objects.create(
            name="Hard Topic", module=module, subject=subject, difficulty_level="hard"
        )

        response = api_client.get("/api/v1/knowledge/topics/?difficulty=easy")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
