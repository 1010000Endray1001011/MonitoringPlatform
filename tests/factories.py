import factory
from factory.django import DjangoModelFactory

from apps.accounts.models import User


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"user{n}@example.com")

    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        self.set_password(extracted or "TestPass123!")
        if create:
            self.save()
