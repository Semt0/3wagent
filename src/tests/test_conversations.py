"""Tests for durable WebUI conversation storage."""

import json

import pytest
from src.agent.conversations import ConversationStore, conversation_title


def test_conversation_title_uses_first_user_text():
    messages = [
        {"role": "assistant", "content": "ignored"},
        {"role": "user", "content": [{"text": "  跨境   税务问题  "}, {"file": "/x"}]},
    ]
    assert conversation_title(messages) == "跨境 税务问题"


def test_store_round_trip_and_updates_without_changing_created_at(tmp_path):
    store = ConversationStore(tmp_path)
    messages = [{"role": "user", "content": [{"text": "你好"}], "name": "user"}]
    conversation_id = store.create(messages)
    first = store.load(conversation_id)

    messages.append({"role": "assistant", "content": "你好，有什么可以帮你？"})
    second = store.save(conversation_id, messages)

    assert second["messages"] == messages
    assert second["title"] == "你好"
    assert second["created_at"] == first["created_at"]
    assert store.list()[0]["id"] == conversation_id


def test_store_ignores_invalid_files_and_rejects_path_traversal(tmp_path):
    store = ConversationStore(tmp_path)
    (tmp_path / "broken.json").write_text("{", encoding="utf-8")
    assert store.list() == []
    with pytest.raises(ValueError):
        store.load("../outside")


def test_store_serializes_model_dump_values(tmp_path):
    class ModelLike:
        def model_dump(self, **_kwargs):
            return {"role": "assistant", "content": "done"}

    store = ConversationStore(tmp_path)
    conversation_id = store.create([ModelLike()])
    payload = json.loads((tmp_path / f"{conversation_id}.json").read_text(encoding="utf-8"))
    assert payload["messages"] == [{"role": "assistant", "content": "done"}]
