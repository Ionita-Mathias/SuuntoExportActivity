from pathlib import Path

from suunto_export_activity.token_store import TokenStore


def test_memory_store_roundtrip() -> None:
    store = TokenStore(path=None, mode="memory")
    token = store.save({"access_token": "abc", "expires_in": 60})

    loaded = store.load()
    assert loaded is not None
    assert loaded.access_token == "abc"
    assert token.expires_at is not None


def test_file_store_roundtrip(tmp_path: Path) -> None:
    token_path = tmp_path / "token.json"
    store = TokenStore(path=token_path, mode="file")
    store.save({"access_token": "abc"})

    reloaded = TokenStore(path=token_path, mode="file").load()
    assert reloaded is not None
    assert reloaded.access_token == "abc"
