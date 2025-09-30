"""
Management command to automatically set up periodic tasks for Celery Beat.
"""
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule
import json


class Command(BaseCommand):
    help = 'Set up periodic tasks for menu fetching and meal plan generation'

    def handle(self, *args, **options):
        self.stdout.write('Setting up periodic tasks...')
        
        # Task 1: Fetch tomorrow's menus at 11 PM daily
        cron_11pm, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='23',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.update_or_create(
            name='Fetch Tomorrow\'s Menus',
            defaults={
                'task': 'menu.tasks.fetch_tomorrow_menus',
                'crontab': cron_11pm,
                'enabled': True,
                'description': 'Fetches next day\'s breakfast, lunch, and dinner menus from HUDS',
            }
        )
        self.stdout.write(self.style.SUCCESS('✓ Created: Fetch Tomorrow\'s Menus (11 PM daily)'))
        
        # Task 2: Breakfast plans at 6:30 AM daily
        cron_630am, _ = CrontabSchedule.objects.get_or_create(
            minute='30',
            hour='6',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.update_or_create(
            name='Generate Breakfast Plans',
            defaults={
                'task': 'users.tasks.generate_and_send_meal_plans',
                'crontab': cron_630am,
                'args': json.dumps(['breakfast']),
                'enabled': True,
                'description': 'Generates and sends breakfast meal plans to all users',
            }
        )
        self.stdout.write(self.style.SUCCESS('✓ Created: Generate Breakfast Plans (6:30 AM daily)'))
        
        # Task 3: Lunch plans at 10:30 AM daily
        cron_1030am, _ = CrontabSchedule.objects.get_or_create(
            minute='30',
            hour='10',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.update_or_create(
            name='Generate Lunch Plans',
            defaults={
                'task': 'users.tasks.generate_and_send_meal_plans',
                'crontab': cron_1030am,
                'args': json.dumps(['lunch']),
                'enabled': True,
                'description': 'Generates and sends lunch meal plans to all users',
            }
        )
        self.stdout.write(self.style.SUCCESS('✓ Created: Generate Lunch Plans (10:30 AM daily)'))
        
        # Task 4: Dinner plans at 3:30 PM daily
        cron_330pm, _ = CrontabSchedule.objects.get_or_create(
            minute='30',
            hour='15',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        PeriodicTask.objects.update_or_create(
            name='Generate Dinner Plans',
            defaults={
                'task': 'users.tasks.generate_and_send_meal_plans',
                'crontab': cron_330pm,
                'args': json.dumps(['dinner']),
                'enabled': True,
                'description': 'Generates and sends dinner meal plans to all users',
            }
        )
        self.stdout.write(self.style.SUCCESS('✓ Created: Generate Dinner Plans (3:30 PM daily)'))
        
        self.stdout.write(self.style.SUCCESS('\n✅ All periodic tasks set up successfully!'))
        self.stdout.write('You can view and manage them in Django admin under Django Celery Beat → Periodic Tasks')
