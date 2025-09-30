"""
Celery tasks for menu app.
"""
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def fetch_tomorrow_menus(target_date=None):
    """
    Fetch tomorrow's menus from HUDS website.
    Scheduled to run nightly at 11:00 PM.
    
    Args:
        target_date: Optional date object. If None, defaults to tomorrow.
    """
    from django.core.management import call_command
    from menu.models import DailyMenu
    
    if target_date is None:
        target_date = date.today() + timedelta(days=1)
    
    logger.info(f"Fetching menus for {target_date}")
    
    try:
        call_command('fetch_daily_menu', date=str(target_date))
        
        # Get stats about what was fetched
        breakfast_count = DailyMenu.objects.filter(date=target_date, meal_type='breakfast').count()
        lunch_count = DailyMenu.objects.filter(date=target_date, meal_type='lunch').count()
        dinner_count = DailyMenu.objects.filter(date=target_date, meal_type='dinner').count()
        
        # Get dish counts
        breakfast_dishes = DailyMenu.objects.filter(date=target_date, meal_type='breakfast').first()
        lunch_dishes = DailyMenu.objects.filter(date=target_date, meal_type='lunch').first()
        dinner_dishes = DailyMenu.objects.filter(date=target_date, meal_type='dinner').first()
        
        stats = {
            'breakfast': breakfast_dishes.dishes.count() if breakfast_dishes else 0,
            'lunch': lunch_dishes.dishes.count() if lunch_dishes else 0,
            'dinner': dinner_dishes.dishes.count() if dinner_dishes else 0,
        }
        stats['total'] = stats['breakfast'] + stats['lunch'] + stats['dinner']
        
        logger.info(f"Successfully fetched menus for {target_date}. Total: {stats['total']} dishes")
        return {
            'status': 'success',
            'date': str(target_date),
            'stats': stats
        }
    except Exception as e:
        logger.error(f"Error fetching menus: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }
