import pytest

from smart360.theory.kb import KnowledgeBase


@pytest.fixture(scope="session")
def kb() -> KnowledgeBase:
    return KnowledgeBase.load()
