"""
Management command to run the Telegram bot.
"""
from django.core.management.base import BaseCommand
from django.conf import settings
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters
import logging

from bot.handlers import (
    start_command,
    help_command,
    nextmeal_command,
    preferences_command,
    goals_command,
    today_command,
    history_command,
    feedback_handler,
    meal_plan_callback,
    fetch_command,
    fetch_date_callback,
    stats_command,
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Run the Telegram bot'

    def handle(self, *args, **options):
        token = settings.TELEGRAM_BOT_TOKEN
        
        if not token:
            self.stdout.write(self.style.ERROR(
                'TELEGRAM_BOT_TOKEN not set in environment variables!'
            ))
            return
        
        self.stdout.write(self.style.SUCCESS('Starting Telegram bot...'))
        
        # Create application
        application = Application.builder().token(token).build()
        
        # Register command handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("nextmeal", nextmeal_command))
        application.add_handler(CommandHandler("preferences", preferences_command))
        application.add_handler(CommandHandler("goals", goals_command))
        application.add_handler(CommandHandler("today", today_command))
        application.add_handler(CommandHandler("history", history_command))
        
        # Admin commands
        application.add_handler(CommandHandler("fetch", fetch_command))
        application.add_handler(CommandHandler("stats", stats_command))
        
        # Register callback handlers with pattern matching
        application.add_handler(CallbackQueryHandler(fetch_date_callback, pattern=r'^fetch_date:'))
        application.add_handler(CallbackQueryHandler(meal_plan_callback, pattern=r'^(accept|modify)_'))
        
        # Register message handler for feedback
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            feedback_handler
        ))
        
        # Run the bot
        self.stdout.write(self.style.SUCCESS('Bot is running! Press Ctrl+C to stop.'))
        application.run_polling(allowed_updates=Update.ALL_TYPES)


# This is needed for the import above
from telegram import Update
