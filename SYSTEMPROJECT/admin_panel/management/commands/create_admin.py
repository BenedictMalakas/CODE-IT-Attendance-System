import hashlib
import uuid
from django.core.management.base import BaseCommand
from myapp.models import Admin


class Command(BaseCommand):
    help = 'Create or reset an admin account for the admin panel.'

    def add_arguments(self, parser):
        parser.add_argument('--email',    default='admin@school.edu')
        parser.add_argument('--password', default='admin123')
        parser.add_argument('--name',     default='Admin User')

    def handle(self, *args, **options):
        email    = options['email']
        password = options['password']
        name     = options['name']
        pw_hash  = hashlib.sha256(password.encode()).hexdigest()

        admin, created = Admin.objects.update_or_create(
            email=email,
            defaults={
                'id':            uuid.uuid4() if not Admin.objects.filter(email=email).exists() else Admin.objects.get(email=email).id,
                'name':          name,
                'password_hash': pw_hash,
                'is_active':     True,
            }
        )

        action = 'Created' if created else 'Updated'
        self.stdout.write(self.style.SUCCESS(
            f'{action} admin:\n  Email:    {email}\n  Password: {password}'
        ))
