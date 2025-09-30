"""
Celery tasks for users app - meal plan generation and notifications.
"""
from celery import shared_task
from django.utils import timezone
from django.conf import settings
from django.contrib.auth.models import User
from datetime import date, datetime
import logging
import sys
import os

# Add huds_lib to path
sys.path.insert(0, os.path.join(settings.BASE_DIR, 'huds_lib'))

from huds_lib.model import create_meal
from users.models import UserProfile, MealPlan, MealPlanDish
from menu.models import DailyMenu, Dish

logger = logging.getLogger(__name__)


@shared_task
def generate_meal_plans_for_meal(meal_type):
    """
    Generate meal plans for all users for a specific meal.
    
    Args:
        meal_type: 'breakfast', 'lunch', or 'dinner'
    """
    today = date.today()
    logger.info(f"Generating {meal_type} plans for {today}")
    
    # Get all active users with notifications enabled
    profiles = UserProfile.objects.filter(
        notifications_enabled=True
    ).select_related('user')
    
    # Filter by meal-specific notification preference
    if meal_type == 'breakfast':
        profiles = profiles.filter(breakfast_notification=True)
    elif meal_type == 'lunch':
        profiles = profiles.filter(lunch_notification=True)
    elif meal_type == 'dinner':
        profiles = profiles.filter(dinner_notification=True)
    
    # Check if daily menu exists
    try:
        daily_menu = DailyMenu.objects.get(date=today, meal_type=meal_type)
    except DailyMenu.DoesNotExist:
        logger.error(f"No {meal_type} menu found for {today}")
        return f"No menu available for {meal_type} on {today}"
    
    plans_created = 0
    for profile in profiles:
        try:
            # Check if plan already exists
            existing_plan = MealPlan.objects.filter(
                user=profile.user,
                daily_menu=daily_menu
            ).first()
            
            if existing_plan:
                logger.info(f"Plan already exists for {profile.user.username}")
                continue
            
            # Get user preferences and feedback
            user_prefs = profile.get_preferences_text()
            feedback_summary = profile.get_feedback_summary(include_weighted_ratings=True)

            # Combine preferences and feedback
            if feedback_summary:
                if user_prefs == "No specific preferences":
                    full_prefs = feedback_summary
                else:
                    full_prefs = f"{user_prefs}. {feedback_summary}"
            else:
                full_prefs = user_prefs

            # Get nutritional goals
            nutritional_goals = {
                'target_calories': profile.target_calories,
                'target_protein': profile.target_protein,
                'target_carbs': profile.target_carbs,
                'target_fat': profile.target_fat,
                'target_fiber': profile.target_fiber,
                'max_sodium': profile.max_sodium,
                'max_added_sugars': profile.max_added_sugars,
            }
            
            # Build menu data from database
            menu_dict = {}
            dishes = daily_menu.dishes.all()
            
            for dish in dishes:
                category = dish.category or 'Other'
                if category not in menu_dict:
                    menu_dict[category] = []
                
                # Build nutrition dict if we have data
                nutrition = None
                if dish.calories > 0:  # Has some nutrition data
                    nutrition = {
                        'name': dish.name,
                        'serving_size': dish.serving_size,
                        'calories': dish.calories,
                        'ingredients': dish.get_ingredients_list(),
                        'nutrition': {
                            'Total Fat': {'amount': f'{dish.total_fat}g', 'daily_value': None},
                            'Saturated Fat': {'amount': f'{dish.saturated_fat}g', 'daily_value': None},
                            'Trans Fat': {'amount': f'{dish.trans_fat}g', 'daily_value': None},
                            'Cholesterol': {'amount': f'{dish.cholesterol}mg', 'daily_value': None},
                            'Sodium': {'amount': f'{dish.sodium}mg', 'daily_value': None},
                            'Total Carbohydrate': {'amount': f'{dish.total_carbohydrate}g', 'daily_value': None},
                            'Dietary Fiber': {'amount': f'{dish.dietary_fiber}g', 'daily_value': None},
                            'Total Sugars': {'amount': f'{dish.total_sugars}g', 'daily_value': None},
                            'Added Sugars': {'amount': f'{dish.added_sugars}g', 'daily_value': None},
                            'Protein': {'amount': f'{dish.protein}g', 'daily_value': None},
                            'Vitamin D': {'amount': f'{dish.vitamin_d}mcg', 'daily_value': None},
                            'Calcium': {'amount': f'{dish.calcium}mg', 'daily_value': None},
                            'Iron': {'amount': f'{dish.iron}mg', 'daily_value': None},
                            'Potassium': {'amount': f'{dish.potassium}mg', 'daily_value': None},
                        }
                    }
                
                menu_dict[category].append({
                    'name': dish.name,
                    'portion': dish.portion_size,
                    'detail_url': dish.detail_url,
                    'nutrition': nutrition,
                    'nutrition_fetch_status': 'success' if nutrition else 'no_data'
                })
            
            menu_data = {
                'metadata': {
                    'date': str(today),
                    'meal': meal_type.capitalize(),
                },
                'menu': menu_dict
            }
            
            # Generate meal plan using AI with database data
            meal_result = create_meal(today, meal_type, full_prefs, menu_data=menu_data, nutritional_goals=nutritional_goals)
            
            # Create meal plan
            meal_plan = MealPlan.objects.create(
                user=profile.user,
                daily_menu=daily_menu,
                explanation=meal_result['explanation'],
                status='pending'
            )
            
            # Create MealPlanDish entries for each selected dish
            for meal_item in meal_result.get('meals', []):
                dish_name = meal_item.get('name', '').strip()
                quantity_str = meal_item.get('quantity', '1')
                
                # Parse quantity to float
                try:
                    if isinstance(quantity_str, (int, float)):
                        quantity = float(quantity_str)
                    else:
                        # Extract first number from string like "1", "2.5", "1 serving"
                        import re
                        match = re.search(r'-?\d+(?:\.\d+)?', str(quantity_str))
                        quantity = float(match.group(0)) if match else 1.0
                except:
                    quantity = 1.0
                
                # Find the dish in the database (case-insensitive)
                try:
                    dish = Dish.objects.get(name__iexact=dish_name)
                    MealPlanDish.objects.create(
                        meal_plan=meal_plan,
                        dish=dish,
                        quantity=quantity
                    )
                except Dish.DoesNotExist:
                    logger.warning(f"Dish '{dish_name}' not found in database for meal plan {meal_plan.id}")
                except Exception as e:
                    logger.error(f"Error creating MealPlanDish for '{dish_name}': {e}")
            
            plans_created += 1
            logger.info(f"Created meal plan for {profile.user.username}")
            
        except Exception as e:
            logger.error(f"Error creating plan for {profile.user.username}: {e}")
            continue
    
    logger.info(f"Created {plans_created} {meal_type} plans")
    return f"Created {plans_created} plans for {meal_type}"


@shared_task
def send_meal_notifications(meal_type):
    """
    Send meal plan notifications via Telegram.
    
    Args:
        meal_type: 'breakfast', 'lunch', or 'dinner'
    """
    from telegram import Bot
    from telegram.error import TelegramError
    import asyncio
    
    today = date.today()
    logger.info(f"Sending {meal_type} notifications for {today}")
    
    # Get unsent meal plans for today
    meal_plans = MealPlan.objects.filter(
        daily_menu__date=today,
        daily_menu__meal_type=meal_type,
        sent_at__isnull=True,
        status='pending'
    ).select_related('user__profile', 'daily_menu')
    
    if not meal_plans.exists():
        logger.info(f"No unsent {meal_type} plans to send")
        return f"No plans to send for {meal_type}"
    
    # Initialize bot
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not configured")
        return "Bot token not configured"
    
    bot = Bot(token=token)
    sent_count = 0
    
    for plan in meal_plans:
        try:
            profile = plan.user.profile
            if not profile.telegram_chat_id:
                logger.warning(f"No chat_id for {plan.user.username}")
                continue
            
            # Format message
            from bot.handlers import format_meal_plan
            message = format_meal_plan(plan)
            
            # Send async message
            asyncio.run(bot.send_message(
                chat_id=profile.telegram_chat_id,
                text=message,
                parse_mode='Markdown'
            ))
            
            # Mark as sent
            plan.sent_at = timezone.now()
            plan.save()
            sent_count += 1
            
            logger.info(f"Sent {meal_type} plan to {plan.user.username}")
            
        except TelegramError as e:
            logger.error(f"Telegram error sending to {plan.user.username}: {e}")
            continue
        except Exception as e:
            logger.error(f"Error sending to {plan.user.username}: {e}")
            continue
    
    logger.info(f"Sent {sent_count} {meal_type} notifications")
    return f"Sent {sent_count} notifications for {meal_type}"


@shared_task
def generate_and_send_meal_plans(meal_type):
    """
    Combined task to generate and send meal plans.
    
    Args:
        meal_type: 'breakfast', 'lunch', or 'dinner'
    """
    # First generate plans
    generate_result = generate_meal_plans_for_meal(meal_type)
    logger.info(f"Generate result: {generate_result}")
    
    # Then send notifications
    send_result = send_meal_notifications(meal_type)
    logger.info(f"Send result: {send_result}")
    
    return f"Generated and sent {meal_type} plans"
