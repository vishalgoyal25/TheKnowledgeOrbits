"""
seed_data.py - Seed the database with initial test content.
"""

import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.dev")
django.setup()


def run():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    print("Seeding database...")
    # Add your seeding logic here
    # Example:
    if not User.objects.filter(email="admin@example.com").exists():
        User.objects.create_superuser("admin@example.com", "admin_password")
        print("Superuser created.")

    print("Database seeding complete.")


if __name__ == "__main__":
    run()
