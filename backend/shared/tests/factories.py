"""Shared Factories for TheKnowledgeOrbits."""

import uuid

from django.contrib.auth import get_user_model

import factory
from factory.django import DjangoModelFactory

from engines.article_generation.models import Article
from engines.assessment.models import Question, Quiz, QuizAttempt
from engines.current_affairs.models import CAArticle, CAChunk, CASource
from engines.knowledge.models import Module, Program, Subject, Topic

User = get_user_model()

# ===== Auth & Knowledge Factories =====


class UserFactory(DjangoModelFactory):
    """Factory for User model."""

    class Meta:
        """Meta configuration."""

        model = User

    id = factory.LazyFunction(uuid.uuid4)
    email = factory.Sequence(lambda n: f"user{n}@example.com")
    full_name = factory.Faker("name")
    is_verified = True
    subscription_tier = "free"

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set user password after generation."""
        if not create:
            return
        if extracted:
            self.set_password(extracted)
        else:
            self.set_password("admin123")


class ProgramFactory(DjangoModelFactory):
    """Factory for Program model."""

    class Meta:
        """Meta configuration."""

        model = Program

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Program {n}")
    description = factory.Faker("text")


class SubjectFactory(DjangoModelFactory):
    """Factory for Subject model."""

    class Meta:
        """Meta configuration."""

        model = Subject

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Subject {n}")
    program = factory.SubFactory(ProgramFactory)


class ModuleFactory(DjangoModelFactory):
    """Factory for Module model."""

    class Meta:
        """Meta configuration."""

        model = Module

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Module {n}")
    subject = factory.SubFactory(SubjectFactory)


class TopicFactory(DjangoModelFactory):
    """Factory for Topic model."""

    class Meta:
        """Meta configuration."""

        model = Topic

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Sequence(lambda n: f"Topic {n}")
    module = factory.SubFactory(ModuleFactory)
    subject = factory.SelfAttribute("module.subject")
    difficulty_level = "medium"


# ===== Current Affairs Factories =====


class CASourceFactory(DjangoModelFactory):
    """Factory for CASource model."""

    class Meta:
        """Meta configuration."""

        model = CASource

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.Faker("company")
    url = factory.Faker("url")


class CAArticleFactory(DjangoModelFactory):
    """Factory for CAArticle model."""

    class Meta:
        """Meta configuration."""

        model = CAArticle

    id = factory.LazyFunction(uuid.uuid4)
    source = factory.SubFactory(CASourceFactory)
    title = factory.Faker("sentence")
    content = factory.Faker("text", max_nb_chars=5000)
    published_at = factory.Faker(
        "date_time_this_month", tzinfo=factory.Faker("timezone")
    )
    url = factory.Sequence(lambda n: f"https://news.com/art-{n}")


class CAChunkFactory(DjangoModelFactory):
    """Factory for CAChunk model."""

    class Meta:
        """Meta configuration."""

        model = CAChunk

    id = factory.LazyFunction(uuid.uuid4)
    ca_article = factory.SubFactory(CAArticleFactory)
    chunk_text = factory.Faker("text", max_nb_chars=1200)
    chunk_index = factory.Sequence(lambda n: n)
    published_at = factory.SelfAttribute("ca_article.published_at")


# ===== Assessment Factories =====


class QuizFactory(DjangoModelFactory):
    """Factory for Quiz model."""

    class Meta:
        """Meta configuration."""

        model = Quiz

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Faker("sentence", nb_words=5)
    topic = factory.SubFactory(TopicFactory)
    difficulty_level = "medium"
    question_count = 10


class QuestionFactory(DjangoModelFactory):
    """Factory for Question model."""

    class Meta:
        """Meta configuration."""

        model = Question

    id = factory.LazyFunction(uuid.uuid4)
    quiz = factory.SubFactory(QuizFactory)
    question_text = factory.Faker("text", max_nb_chars=200)
    question_type = "single_mcq"
    options = {"A": "Option 1", "B": "Option 2", "C": "Option 3", "D": "Option 4"}
    correct_answer = "A"
    explanation = factory.Faker("text")


class QuizAttemptFactory(DjangoModelFactory):
    """Factory for QuizAttempt model."""

    class Meta:
        """Meta configuration."""

        model = QuizAttempt

    id = factory.LazyFunction(uuid.uuid4)
    quiz = factory.SubFactory(QuizFactory)
    user = factory.SubFactory(UserFactory)
    status = "submitted"
    score = 75.0


# ===== Article Factories =====


class ArticleFactory(DjangoModelFactory):
    """Factory for Article model."""

    class Meta:
        """Meta configuration."""

        model = Article

    id = factory.LazyFunction(uuid.uuid4)
    title = factory.Faker("sentence")
    content = factory.Faker("text", max_nb_chars=2000)
    topic = factory.SubFactory(TopicFactory)
    is_published = True
