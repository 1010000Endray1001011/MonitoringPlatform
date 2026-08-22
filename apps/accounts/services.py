from .models import User


def register_user(*, email: str, password: str) -> User:
    return User.objects.create_user(email=email.strip().lower(), password=password)
