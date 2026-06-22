"""One-off generator for the synthetic demo users (SS-34).

Run from the repo root to (re)write sprintsight/web/auth/seed_users.yaml. The
demo passwords are intentionally simple: the users are synthetic and the app is
single-tenant on synthetic data. Passwords are documented in HANDOVER.
"""

from pathlib import Path

import yaml

from sprintsight.web.auth.hashing import hash_password, new_salt

DEMO_USERS = [
    ("admin@sprintsight.test", "admin", "admin-watermelon"),
    ("manager@sprintsight.test", "delivery_manager", "manager-watermelon"),
    ("viewer@sprintsight.test", "viewer", "viewer-watermelon"),
]

OUT = (
    Path(__file__).resolve().parents[1]
    / "sprintsight"
    / "web"
    / "auth"
    / "seed_users.yaml"
)


def main() -> None:
    records = []
    for email, role, password in DEMO_USERS:
        salt = new_salt()
        records.append(
            {
                "email": email,
                "role": role,
                "salt": salt,
                "hash": hash_password(password, salt),
            }
        )
    OUT.write_text(yaml.safe_dump(records, sort_keys=False))
    print(f"wrote {OUT} with {len(records)} users")


if __name__ == "__main__":
    main()
