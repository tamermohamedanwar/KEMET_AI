import pytest

from wsgi import application
from app import db
from app.models.organization import Organization
from app.models.user import User
from app.models.conversation import Conversation
from app.models.document import Document
from app.services.chat_service import ChatService
from app.rag.indexer import RAGIndexer


@pytest.fixture(autouse=True)
def app_context():
    with application.app_context():
        yield


def make_tenant(suffix):
    org = Organization(name=f"tenant-{suffix}", slug=f"tenant-{suffix}")
    db.session.add(org)
    db.session.flush()
    user = User(
        organization_id=org.id,
        full_name=f"User {suffix}",
        email=f"user-{suffix}@example.test",
        password_hash="test",
    )
    db.session.add(user)
    db.session.commit()
    return org, user


def test_chat_rejects_cross_tenant_conversation():
    org_a, user_a = make_tenant("a")
    org_b, user_b = make_tenant("b")
    conversation = Conversation(
        user_id=user_a.id,
        organization_id=org_a.id,
        title="A",
    )
    db.session.add(conversation)
    db.session.commit()

    with pytest.raises(ValueError, match="conversation_not_found"):
        ChatService().generate_reply(
            "cross tenant",
            user_id=user_b.id,
            organization_id=org_b.id,
            conversation_id=conversation.id,
        )


def test_new_chat_persists_tenant(monkeypatch):
    org, user = make_tenant("c")
    monkeypatch.setattr(
        "app.services.chat_service.ask_ai",
        lambda *args, **kwargs: "ok",
    )
    _, conversation_id = ChatService().generate_reply(
        "hello", user_id=user.id, organization_id=org.id
    )
    conversation = db.session.get(Conversation, conversation_id)
    assert conversation.organization_id == org.id
    assert conversation.user_id == user.id


def test_rag_rejects_cross_tenant_document():
    org_a, user_a = make_tenant("d")
    org_b, user_b = make_tenant("e")
    conversation = Conversation(
        user_id=user_a.id,
        organization_id=org_a.id,
        title="A document chat",
    )
    db.session.add(conversation)
    db.session.flush()
    document = Document(
        organization_id=org_a.id,
        conversation_id=conversation.id,
        filename="a.txt",
        file_type="txt",
        file_size=1,
    )
    db.session.add(document)
    db.session.commit()

    with pytest.raises(ValueError, match="document_not_found_or_tenant_mismatch"):
        RAGIndexer().add_document(document.id, ["secret"], org_b.id)
