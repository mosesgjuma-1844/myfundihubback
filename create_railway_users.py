import os
import sys

# Configure Django settings module for direct execution
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'fundi_backend.settings')

import django

django.setup()

from django.contrib.auth.models import User


def create_or_update_user(username: str, email: str, password: str, is_staff: bool = False, is_superuser: bool = False):
    user, created = User.objects.get_or_create(username=username, defaults={'email': email})
    if not created:
        user.email = email
    user.set_password(password)
    user.is_staff = is_staff
    user.is_superuser = is_superuser
    user.save()
    return created, user


def main():
    users = [
        {
            'username': 'mosesgjuma',
            'email': 'mosesgjuma@gmail.com',
            'password': 'Hub@123456',
            'is_staff': False,
            'is_superuser': False,
        },
        {
            'username': 'admin',
            'email': 'mosesgjuma@gmail.com',
            'password': 'Hub@123456',
            'is_staff': True,
            'is_superuser': True,
        },
    ]

    for user_data in users:
        created, user = create_or_update_user(
            username=user_data['username'],
            email=user_data['email'],
            password=user_data['password'],
            is_staff=user_data['is_staff'],
            is_superuser=user_data['is_superuser'],
        )
        action = 'Created' if created else 'Updated'
        print(f"{action} user '{user.username}' (email={user.email}, superuser={user.is_superuser})")


if __name__ == '__main__':
    main()
