"""
Celery tasks for menu app.
"""
from celery import shared_task
from django.utils import timezone
from datetime import date, timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def fetch_tomorrow_menus():
    """
    Fetch tomorrow's menus from HUDS website.
    Scheduled to run nightly at 11:00 PM.
    """
    from django.core.management import call_command
    
    tomorrow = date.today() + timedelta(days=1)
    logger.info(f"Fetching menus for {tomorrow}")
    
    try:
        call_command('fetch_daily_menu', date=str(tomorrow))
        logger.info("Successfully fetched tomorrow's menus")
        return f"Fetched menus for {tomorrow}"
    except Exception as e:
        logger.error(f"Error fetching menus: {e}")
        raise
