import jwt
import pytest

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_access_token,
    decode_refresh_token,
    generate_invitation_token,
    hash_invitation_token,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("correct horse battery staple")

    assert verify_password("correct horse battery staple", hashed)
    assert not verify_password("wrong password", hashed)


def test_access_token_roundtrip() -> None:
    token = create_access_token("user-1", "ADMIN")

    payload = decode_access_token(token)

    assert payload["sub"] == "user-1"
    assert payload["role"] == "ADMIN"


def test_refresh_token_roundtrip() -> None:
    token = create_refresh_token("user-1")

    payload = decode_refresh_token(token)

    assert payload["sub"] == "user-1"


def test_access_decoder_rejects_a_refresh_token() -> None:
    token = create_refresh_token("user-1")

    with pytest.raises(jwt.PyJWTError):
        decode_access_token(token)


def test_refresh_decoder_rejects_an_access_token() -> None:
    token = create_access_token("user-1", "EMPLOYEE")

    with pytest.raises(jwt.PyJWTError):
        decode_refresh_token(token)


def test_invitation_token_hash_is_deterministic_and_unguessable() -> None:
    raw_token, token_hash = generate_invitation_token()

    assert hash_invitation_token(raw_token) == token_hash
    assert hash_invitation_token("a-different-token") != token_hash

    other_raw_token, other_hash = generate_invitation_token()
    assert other_raw_token != raw_token
    assert other_hash != token_hash
