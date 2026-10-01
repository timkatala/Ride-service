from src.core.security import is_valid_signature, sign


def test_valid_signature():
    body = b'{"status": "accepted"}'
    assert is_valid_signature("secret", body, sign("secret", body))


def test_signature_with_wrong_secret_or_body():
    body = b'{"status": "accepted"}'
    assert not is_valid_signature("secret", body, sign("other-secret", body))
    assert not is_valid_signature("secret", b'{"status": "completed"}', sign("secret", body))


def test_missing_signature():
    assert not is_valid_signature("secret", b"{}", None)
    assert not is_valid_signature("secret", b"{}", "")
