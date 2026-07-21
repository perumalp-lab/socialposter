"""Create a new admin user, or promote/reset-password an existing one.

Usage:
    python scripts/create_admin.py

Prompts for email and password locally (password input is hidden).
If the email already exists, it is promoted to admin and (optionally) its
password is reset. Otherwise a new admin account is created.
"""

from __future__ import annotations

import getpass

from socialposter.web.app import create_app
from socialposter.web.models import User, Team, TeamMember, db


def main() -> None:
    app = create_app()
    with app.app_context():
        email = input("Admin email: ").strip().lower()
        if not email:
            print("Aborted: email is required.")
            return

        user = User.query.filter_by(email=email).first()

        if user:
            print(f"User '{email}' already exists — promoting to admin.")
            user.is_admin = True
            reset = input("Reset password too? [y/N]: ").strip().lower()
            if reset == "y":
                pw = getpass.getpass("New password (min 8 chars): ")
                if len(pw) < 8:
                    print("Aborted: password must be at least 8 characters.")
                    return
                user.set_password(pw)
        else:
            pw = getpass.getpass("Password (min 8 chars): ")
            if len(pw) < 8:
                print("Aborted: password must be at least 8 characters.")
                return
            name = email.split("@")[0]
            user = User(email=email, display_name=name, is_admin=True, timezone="UTC")
            user.set_password(pw)
            db.session.add(user)
            db.session.flush()

            # Give the new admin a personal workspace so team-gated APIs work.
            team = Team(name=f"{name}'s workspace", slug=f"{name}-workspace",
                        created_by=user.id)
            db.session.add(team)
            db.session.flush()
            db.session.add(TeamMember(team_id=team.id, user_id=user.id, role="admin"))
            print(f"Created new admin '{email}'.")

        db.session.commit()
        print(f"Done. {email} | is_admin={user.is_admin}")


if __name__ == "__main__":
    main()
