from sprintsight.web.auth.hashing import hash_password, new_salt, verify_password


def test_verify_accepts_correct_password():
    salt = new_salt()
    h = hash_password("correct horse", salt)
    assert verify_password("correct horse", salt, h) is True


def test_verify_rejects_wrong_password():
    salt = new_salt()
    h = hash_password("correct horse", salt)
    assert verify_password("battery staple", salt, h) is False


def test_new_salt_is_random_and_changes_hash():
    s1, s2 = new_salt(), new_salt()
    assert s1 != s2
    assert hash_password("pw", s1) != hash_password("pw", s2)


def test_hash_is_deterministic_for_same_salt():
    salt = new_salt()
    assert hash_password("pw", salt) == hash_password("pw", salt)


def test_verify_returns_false_on_corrupt_salt():
    # non-hex salt must fail closed (False), not raise
    assert verify_password("pw", "not-hex-salt", "deadbeef") is False
