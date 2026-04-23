from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.invite import InviteToken
from app.models.password_reset import PasswordResetToken


def test_invite_token_hash_is_unique(db_session):
    now = datetime.now(timezone.utc)
    tok = "same"
    i1 = InviteToken(
        email="a@test.local",
        token_hash=tok,
        expires_at=now + timedelta(days=1),
    )
    i2 = InviteToken(
        email="b@test.local",
        token_hash=tok,
        expires_at=now + timedelta(days=1),
    )
    db_session.add(i1)
    db_session.commit()
    db_session.add(i2)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_password_reset_token_hash_is_unique(db_session):
    now = datetime.now(timezone.utc)
    tok = "same"
    r1 = PasswordResetToken(
        email="a@test.local",
        token_hash=tok,
        expires_at=now + timedelta(minutes=10),
    )
    r2 = PasswordResetToken(
        email="b@test.local",
        token_hash=tok,
        expires_at=now + timedelta(minutes=10),
    )
    db_session.add(r1)
    db_session.commit()
    db_session.add(r2)
    with pytest.raises(IntegrityError):
        db_session.commit()
