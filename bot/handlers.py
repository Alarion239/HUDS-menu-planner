"""
Telegram bot handlers for user interactions.
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from django.contrib.auth.models import User
from users.models import UserProfile, MealPlan, UserFeedback, MealHistory, MealPlanDish
from menu.models import Dish, DailyMenu
from datetime import date, datetime, time
from asgiref.sync import sync_to_async
from django.conf import settings
import logging
import sys
import os
import re

logger = logging.getLogger(__name__)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - register new user"""
    chat_id = update.effective_chat.id
    username = update.effective_user.username or f"user_{chat_id}"
    
    # Get or create Django user (wrapped in sync_to_async)
    user, created = await sync_to_async(User.objects.get_or_create)(
        username=username,
        defaults={'first_name': update.effective_user.first_name or ''}
    )
    
    # Get or create user profile
    profile, profile_created = await sync_to_async(UserProfile.objects.get_or_create)(
        user=user,
        defaults={
            'telegram_chat_id': chat_id,
            'telegram_username': username
        }
    )
    
    if profile_created or not profile.telegram_chat_id:
        profile.telegram_chat_id = chat_id
        profile.telegram_username = username
        await sync_to_async(profile.save)()
    
    if created:
        message = (
            f"👋 Welcome to HUDS Menu Planner, {update.effective_user.first_name}!\n\n"
            f"I'll help you plan balanced meals from the HUDS menu.\n\n"
            f"📋 Available commands:\n"
            f"/nextmeal - Generate next meal plan now\n"
            f"/preferences - Set dietary restrictions\n"
            f"/goals - Set nutritional goals\n"
            f"/today - Get today's meal plans\n"
            f"/feedback - Provide feedback on meals\n"
            f"/history - View your meal history\n"
            f"/help - Show all commands\n\n"
            f"You'll receive meal recommendations before each meal time!"
        )
    else:
        message = (
            f"👋 Welcome back, {update.effective_user.first_name}!\n\n"
            f"Use /help to see available commands."
        )
    
    await update.message.reply_text(message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    chat_id = update.effective_chat.id
    
    # Check if user is admin
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
        is_admin = profile.is_admin
    except UserProfile.DoesNotExist:
        is_admin = False
    
    message = (
        "🍽️ **HUDS Menu Planner**\n\n"
        "**Commands:**\n"
        "/start - Register or re-register\n"
        "/nextmeal - Generate next meal plan now\n"
        "/logmeal - Log what you actually ate (free-form text)\n"
        "/preferences - Update dietary restrictions\n"
        "/goals - Set nutritional goals\n"
        "/today - Get today's meal plans\n"
        "/feedback <dish> - Rate a dish\n"
        "/history - View meal history\n"
        "/help - Show this message\n\n"
        "**Meal Times:**\n"
        "🌅 Breakfast: 7:30 AM to 10:30 AM\n"
        "🌞 Lunch: 11:30 AM to 2:00 PM\n"
        "🌙 Dinner: 4:30 PM to 7:30 PM\n\n"
        "I'll send you personalized meal plans before each meal!\n"
        "Or use /nextmeal to generate one on demand.\n"
        "After eating, use /logmeal to track what you actually ate."
    )
    
    if is_admin:
        message += (
            "\n\n**Admin Commands:**\n"
            "/fetch - Manually fetch menus (interactive date picker)\n"
            "/stats - View system statistics"
        )
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def preferences_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /preferences command"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    if context.args:
        # Update preferences
        new_prefs = ' '.join(context.args)
        profile.dietary_restrictions = new_prefs
        await sync_to_async(profile.save)()
        await update.message.reply_text(
            f"✅ Updated dietary restrictions to:\n{new_prefs}"
        )
    else:
        # Show current preferences
        current = profile.dietary_restrictions or "None set"
        await update.message.reply_text(
            f"Current dietary restrictions:\n{current}\n\n"
            f"To update, use:\n/preferences your restrictions here"
        )


async def goals_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /goals command"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    # Show current goals
    message = (
        "🎯 **Your Nutritional Goals:**\n\n"
        f"Calories: {profile.target_calories} kcal\n"
        f"Protein: {profile.target_protein}g\n"
        f"Carbs: {profile.target_carbs}g\n"
        f"Fat: {profile.target_fat}g\n"
        f"Fiber: {profile.target_fiber}g\n"
        f"Max Sodium: {profile.max_sodium}mg\n"
        f"Max Added Sugars: {profile.max_added_sugars}g\n\n"
        f"To modify goals, please use the web admin interface."
    )
    await update.message.reply_text(message, parse_mode='Markdown')


async def today_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /today command - show today's meal plans"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    today = date.today()
    
    # Get meal plans using sync_to_async
    @sync_to_async
    def get_meal_plans():
        return list(MealPlan.objects.filter(
            user=profile.user,
            daily_menu__date=today
        ).select_related('daily_menu'))
    
    meal_plans = await get_meal_plans()
    
    if not meal_plans:
        await update.message.reply_text(
            "No meal plans for today yet. They'll be sent before each meal time!"
        )
        return
    
    for plan in meal_plans:
        message = await format_meal_plan_async(plan)
        await update.message.reply_text(message, parse_mode='Markdown')


async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    # Get recent meal history (last 7 days)
    @sync_to_async
    def get_recent_meals():
        return list(MealHistory.objects.filter(
            user=profile.user
        ).select_related('dish', 'daily_menu').order_by('-eaten_at')[:20])
    
    recent_meals = await get_recent_meals()
    
    if not recent_meals:
        await update.message.reply_text(
            "No meal history yet. Your meals will be tracked here!"
        )
        return
    
    message = "📊 **Recent Meal History:**\n\n"
    for meal in recent_meals:
        date_str = meal.eaten_at.strftime("%b %d, %Y %I:%M %p")
        message += f"• {meal.dish.name} ({meal.quantity}x) - {date_str}\n"
    
    await update.message.reply_text(message, parse_mode='Markdown')


async def nextmeal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nextmeal command - generate next meal on demand"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    # Determine which meal to generate based on current time
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    # Time-based meal determination:
    # Before 11:00 → Breakfast
    # 11:00 - 15:00 → Lunch
    # 15:00 - 22:00 → Dinner
    # After 22:00 → Next day's breakfast
    
    if current_time < time(11, 0):
        # Before 11 AM → Breakfast
        next_meal = 'breakfast'
        meal_date = today
    elif current_time < time(15, 0):
        # 11 AM - 3 PM → Lunch
        next_meal = 'lunch'
        meal_date = today
    elif current_time < time(22, 0):
        # 3 PM - 10 PM → Dinner
        next_meal = 'dinner'
        meal_date = today
    else:
        # After 10 PM → Tomorrow's breakfast
        from datetime import timedelta
        next_meal = 'breakfast'
        meal_date = today + timedelta(days=1)
    
    generating_msg = await update.message.reply_text(
        f"🔄 Generating your {next_meal} plan..."
    )
    
    # Check if menu exists
    @sync_to_async
    def get_daily_menu():
        try:
            return DailyMenu.objects.get(date=meal_date, meal_type=next_meal)
        except DailyMenu.DoesNotExist:
            return None
    
    daily_menu = await get_daily_menu()
    
    if not daily_menu:
        await generating_msg.edit_text(
            f"❌ The {next_meal} menu for {meal_date} isn't available yet.\n"
            f"Menus are fetched the night before. Try again later!"
        )
        return
    
    # Check if plan already exists
    @sync_to_async
    def get_existing_plan():
        return MealPlan.objects.filter(
            user=profile.user,
            daily_menu=daily_menu
        ).first()
    
    existing_plan = await get_existing_plan()
    
    if existing_plan:
        # Show existing plan
        message = await format_meal_plan_async(existing_plan)
        await generating_msg.edit_text(
            message,
            parse_mode='Markdown'
        )
        return
    
    # Generate new plan using AI
    try:
        # Import and use the meal planning function
        sys.path.insert(0, os.path.join(settings.BASE_DIR, 'huds_lib'))
        from huds_lib.model import create_meal
        
        # Get user preferences and feedback
        user_prefs = await sync_to_async(profile.get_preferences_text)()
        feedback_summary = await sync_to_async(lambda: profile.get_feedback_summary(include_weighted_ratings=True))()

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
        @sync_to_async
        def build_menu_data():
            """Convert database menu to format expected by create_meal()"""
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
            
            return {
                'metadata': {
                    'date': str(meal_date),
                    'meal': next_meal.capitalize(),
                },
                'menu': menu_dict
            }
        
        menu_data = await build_menu_data()
        
        # Generate meal plan (this runs the AI)
        @sync_to_async
        def generate_plan():
            # Create meal returns structured data now
            meal_result = create_meal(meal_date, next_meal, full_prefs, menu_data=menu_data, nutritional_goals=nutritional_goals)
            
            # Create meal plan record
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
            
            return meal_plan
        
        meal_plan = await generate_plan()
        
        # Format and send the plan with action buttons
        message = await format_meal_plan_async(meal_plan)
        
        # Create inline keyboard with Accept/Modify buttons
        keyboard = [
            [
                InlineKeyboardButton("✅ Accept", callback_data=f"accept_{meal_plan.id}"),
                InlineKeyboardButton("🔄 Modify", callback_data=f"modify_{meal_plan.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await generating_msg.edit_text(
            message,
            parse_mode='Markdown',
            reply_markup=reply_markup
        )
        
    except Exception as e:
        logger.error(f"Error generating meal plan: {e}")
        await generating_msg.edit_text(
            f"❌ Error generating meal plan.\n"
            f"Please try again later."
        )


async def logmeal_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /logmeal command - log actual meal eaten using free-form text"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    # Get the meal description from the message
    if not context.args:
        await update.message.reply_text(
            "📝 **Log Your Meal**\n\n"
            "Describe what you ate in free-form text. I'll parse it and track the nutrition!\n\n"
            "**Examples:**\n"
            "• `/logmeal I ate a chicken breast and a side salad`\n"
            "• `/logmeal Half a waffle with strawberries and yogurt`\n"
            "• `/logmeal Two slices of pizza and a coke`\n\n"
            "I'll match items to HUDS menu dishes and calculate your nutrition.",
            parse_mode='Markdown'
        )
        return
    
    meal_description = ' '.join(context.args)
    
    # Send processing message
    processing_msg = await update.message.reply_text(
        "🤔 Analyzing your meal..."
    )
    
    # Get current time for fallback
    now = datetime.now()
    today = now.date()
    current_time = now.time()
    
    # Process the meal description using AI
    @sync_to_async
    def parse_and_log_meal():
        """Parse meal description and create meal records"""
        try:
            sys.path.insert(0, os.path.join(settings.BASE_DIR, 'huds_lib'))
            from openai import OpenAI
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Get available dishes from recent menus (last 7 days)
            from datetime import timedelta
            from django.utils import timezone as django_tz
            seven_days_ago = django_tz.now() - timedelta(days=7)
            
            recent_dishes = Dish.objects.filter(
                menus__date__gte=seven_days_ago
            ).distinct().values_list('name', flat=True).order_by('name')[:300]
            
            available_dishes_list = "\n".join([f"- {dish}" for dish in recent_dishes])
            
            # Ask GPT to extract dish names, quantities, and meal type
            prompt = f"""Parse this meal description and extract information.

User said: "{meal_description}"
Current time: {current_time.strftime('%I:%M %p')} (use as fallback if meal not mentioned)

Available HUDS dishes (use EXACT names from this list):
{available_dishes_list}

Extract:
1. Meal type: breakfast, lunch, or dinner (look for keywords like "breakfast", "lunch", "dinner" in the text; if not mentioned, infer from time: before 11am=breakfast, 11am-3pm=lunch, after 3pm=dinner)
2. Each dish mentioned with quantity
3. For dishes NOT in the list, find 2-3 closest matches to suggest

Return ONLY valid JSON:
{{
  "meal_type": "breakfast|lunch|dinner",
  "items": [
    {{"name": "Exact Dish Name", "quantity": 1.0, "confidence": "high"}}
  ],
  "unclear_items": [
    {{
      "user_mentioned": "what user said",
      "quantity": 1.0,
      "suggestions": ["Similar Dish 1", "Similar Dish 2", "Similar Dish 3"]
    }}
  ]
}}

Rules:
- Detect meal type from user's text (e.g., "for lunch" → lunch)
- Parse quantities: half=0.5, two=2.0, one=1.0, default=1.0
- ONLY use exact dish names from the provided list for "items"
- For unclear dishes, provide 2-3 similar suggestions from the list
- Match dishes case-insensitively but use exact capitalization from list"""
            
            model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
            )
            
            result = response.choices[0].message.content
            
            # Parse JSON response
            import json
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                import re
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract valid JSON from AI response")
            
            items = data.get('items', [])
            unclear_items = data.get('unclear_items', [])
            meal_type = data.get('meal_type', '').lower()
            
            # Validate meal type
            if meal_type not in ['breakfast', 'lunch', 'dinner']:
                # Fallback to time-based detection
                if current_time < time(11, 0):
                    meal_type = 'breakfast'
                elif current_time < time(15, 0):
                    meal_type = 'lunch'
                else:
                    meal_type = 'dinner'
            
            # If there are unclear items, return them for user confirmation
            if unclear_items:
                return {
                    'success': True,
                    'needs_confirmation': True,
                    'meal_type': meal_type,
                    'items': items,
                    'unclear_items': unclear_items,
                    'meal_description': meal_description
                }
            
            # Find or create today's daily menu for this meal
            daily_menu, _ = DailyMenu.objects.get_or_create(
                date=today,
                meal_type=meal_type,
                defaults={}
            )
            
            # Delete any existing meal plan for this user/meal combination
            # This handles both proposed and previously completed meals
            existing_plans = MealPlan.objects.filter(
                user=profile.user,
                daily_menu=daily_menu
            )
            
            if existing_plans.exists():
                plan_action = "updated"
                existing_plans.delete()
            else:
                plan_action = "created"
            
            # Create new completed meal plan
            meal_plan = MealPlan.objects.create(
                user=profile.user,
                daily_menu=daily_menu,
                explanation=f"Actual meal logged: {meal_description}",
                status='completed',
                completed_at=django_tz.now()
            )
            
            # Add dishes to meal plan and create meal history
            found_dishes = []
            not_found_dishes = []
            total_nutrition = {
                'calories': 0,
                'protein': 0,
                'carbs': 0,
                'fat': 0,
                'fiber': 0,
                'sodium': 0,
                'sugars': 0
            }
            
            for item in items:
                dish_name = item.get('name', '').strip()
                quantity = float(item.get('quantity', 1.0))
                
                if not dish_name:
                    continue
                
                # Try to find the dish (case-insensitive)
                try:
                    dish = Dish.objects.get(name__iexact=dish_name)
                    
                    # Create MealPlanDish entry
                    MealPlanDish.objects.create(
                        meal_plan=meal_plan,
                        dish=dish,
                        quantity=quantity
                    )
                    
                    # Create MealHistory entry
                    MealHistory.objects.create(
                        user=profile.user,
                        dish=dish,
                        daily_menu=daily_menu,
                        meal_plan=meal_plan,
                        quantity=quantity,
                        eaten_at=django_tz.now()
                    )
                    
                    found_dishes.append({
                        'name': dish.name,
                        'quantity': quantity,
                        'calories': dish.calories * quantity
                    })
                    
                    # Add to nutrition totals
                    total_nutrition['calories'] += dish.calories * quantity
                    total_nutrition['protein'] += dish.protein * quantity
                    total_nutrition['carbs'] += dish.total_carbohydrate * quantity
                    total_nutrition['fat'] += dish.total_fat * quantity
                    total_nutrition['fiber'] += dish.dietary_fiber * quantity
                    total_nutrition['sodium'] += dish.sodium * quantity
                    total_nutrition['sugars'] += dish.total_sugars * quantity
                    
                    logger.info(f"Logged meal: {dish.name} x{quantity} for {profile.user.username}")
                    
                except Dish.DoesNotExist:
                    not_found_dishes.append({
                        'name': dish_name,
                        'quantity': quantity
                    })
                    logger.warning(f"Dish '{dish_name}' not found for meal logging")
            
            return {
                'success': True,
                'needs_confirmation': False,
                'plan_action': plan_action,
                'meal_type': meal_type,
                'found_dishes': found_dishes,
                'not_found_dishes': not_found_dishes,
                'total_nutrition': total_nutrition
            }
            
        except Exception as e:
            logger.error(f"Error parsing meal: {e}")
            return {'success': False, 'error': str(e)}
    
    result = await parse_and_log_meal()
    
    if not result.get('success'):
        await processing_msg.edit_text(
            f"❌ Sorry, I had trouble processing your meal:\n{result.get('error', 'Unknown error')}\n\n"
            "Please try again or contact support."
        )
        return
    
    # Handle unclear items - ask for confirmation
    if result.get('needs_confirmation'):
        await _handle_unclear_items(update, context, processing_msg, result, profile, chat_id)
        return
    
    # Format the response
    meal_emoji = {
        'breakfast': '🌅',
        'lunch': '🌞',
        'dinner': '🌙'
    }
    emoji = meal_emoji.get(result['meal_type'], '🍽️')
    
    message = f"{emoji} **Meal Logged** - {result['meal_type'].capitalize()}\n\n"
    
    if result['plan_action'] == 'updated':
        message += "✅ Updated your proposed meal plan with what you actually ate\n\n"
    else:
        message += "✅ Created new meal record\n\n"
    
    # List found dishes
    if result['found_dishes']:
        message += "**What you ate:**\n"
        for item in result['found_dishes']:
            qty_text = ""
            if item['quantity'] == 0.5:
                qty_text = "½ "
            elif item['quantity'] != 1.0:
                qty_text = f"{item['quantity']}× "
            
            cal_text = f" ({int(item['calories'])} cal)" if item['calories'] > 0 else ""
            message += f"• {qty_text}{item['name']}{cal_text}\n"
    
    # Show nutrition totals
    nutrition = result['total_nutrition']
    message += f"\n📊 **Total Nutrition:**\n"
    message += f"Calories: {int(nutrition['calories'])} kcal\n"
    message += f"Protein: {int(nutrition['protein'])}g | "
    message += f"Carbs: {int(nutrition['carbs'])}g | "
    message += f"Fat: {int(nutrition['fat'])}g\n"
    message += f"Fiber: {int(nutrition['fiber'])}g | "
    message += f"Sodium: {int(nutrition['sodium'])}mg | "
    message += f"Sugars: {int(nutrition['sugars'])}g"
    
    # Warn about not found dishes
    if result['not_found_dishes']:
        message += "\n\n⚠️ **Couldn't find:**\n"
        for item in result['not_found_dishes']:
            message += f"• {item['name']}\n"
        message += "\nThese weren't included in nutrition totals."
    
    await processing_msg.edit_text(message, parse_mode='Markdown')


async def _handle_unclear_items(update, context, processing_msg, result, profile, chat_id):
    """Handle unclear items by asking user to select from suggestions"""
    unclear_items = result.get('unclear_items', [])
    items = result.get('items', [])
    meal_type = result.get('meal_type', 'lunch')
    
    # Store data in context for callback
    if 'logmeal_data' not in context.user_data:
        context.user_data['logmeal_data'] = {}
    
    context.user_data['logmeal_data'] = {
        'items': items,
        'meal_type': meal_type,
        'unclear_items': unclear_items,
        'meal_description': result.get('meal_description', ''),
        'chat_id': chat_id
    }
    
    # Build message with suggestions
    meal_emoji = {
        'breakfast': '🌅',
        'lunch': '🌞',
        'dinner': '🌙'
    }
    emoji = meal_emoji.get(meal_type, '🍽️')
    
    message = f"{emoji} **Confirming {meal_type.capitalize()} Items**\n\n"
    message += "I found some items that need clarification:\n\n"
    
    # Show confirmed items
    if items:
        message += "✅ **Confirmed:**\n"
        for item in items:
            qty = item.get('quantity', 1.0)
            qty_text = f"{qty}× " if qty != 1.0 else ""
            message += f"• {qty_text}{item['name']}\n"
        message += "\n"
    
    # Show unclear items with numbered options
    message += "❓ **Please select the correct dish for each item:**\n\n"
    
    # Create keyboard buttons for first unclear item
    if unclear_items:
        first_unclear = unclear_items[0]
        user_mentioned = first_unclear.get('user_mentioned', 'item')
        suggestions = first_unclear.get('suggestions', [])
        qty = first_unclear.get('quantity', 1.0)
        
        qty_text = f"{qty}× " if qty != 1.0 else ""
        message += f"You said: **{qty_text}{user_mentioned}**\n"
        message += "Did you mean:\n"
        
        keyboard = []
        for i, suggestion in enumerate(suggestions[:3]):  # Max 3 suggestions
            keyboard.append([
                InlineKeyboardButton(
                    f"✓ {suggestion}",
                    callback_data=f"logmeal_select:{i}:{suggestion[:30]}"  # Limit callback data length
                )
            ])
        
        # Add "Skip this item" button
        keyboard.append([
            InlineKeyboardButton(
                "⏭ Skip this item",
                callback_data="logmeal_skip:0"
            )
        ])
        
        # Add "Cancel" button
        keyboard.append([
            InlineKeyboardButton(
                "❌ Cancel meal logging",
                callback_data="logmeal_cancel"
            )
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await processing_msg.edit_text(message, parse_mode='Markdown', reply_markup=reply_markup)
    else:
        await processing_msg.edit_text(
            "❌ No suggestions available. Please try again with different dish names."
        )


async def logmeal_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle meal logging confirmation callbacks"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    
    # Get stored meal data
    meal_data = context.user_data.get('logmeal_data', {})
    if not meal_data:
        await query.edit_message_text("❌ Session expired. Please use /logmeal again.")
        return
    
    items = meal_data.get('items', [])
    unclear_items = meal_data.get('unclear_items', [])
    meal_type = meal_data.get('meal_type', 'lunch')
    chat_id = meal_data.get('chat_id')
    
    if callback_data == "logmeal_cancel":
        # User cancelled
        await query.edit_message_text("❌ Meal logging cancelled.")
        context.user_data.pop('logmeal_data', None)
        return
    
    elif callback_data.startswith("logmeal_select:"):
        # User selected a dish
        _, idx_str, _ = callback_data.split(':', 2)
        idx = int(idx_str)
        
        if unclear_items:
            first_unclear = unclear_items[0]
            suggestions = first_unclear.get('suggestions', [])
            
            if idx < len(suggestions):
                # Add selected dish to confirmed items
                selected_dish = suggestions[idx]
                items.append({
                    'name': selected_dish,
                    'quantity': first_unclear.get('quantity', 1.0)
                })
            
            # Remove this unclear item
            unclear_items.pop(0)
            
            # Update stored data
            meal_data['items'] = items
            meal_data['unclear_items'] = unclear_items
            context.user_data['logmeal_data'] = meal_data
            
            # If more unclear items, show next one
            if unclear_items:
                await _show_next_unclear_item(query, meal_data)
            else:
                # All items confirmed, proceed with logging
                await _finalize_meal_logging(query, context, meal_data, chat_id)
    
    elif callback_data.startswith("logmeal_skip:"):
        # User skipped this item
        if unclear_items:
            unclear_items.pop(0)
            meal_data['unclear_items'] = unclear_items
            context.user_data['logmeal_data'] = meal_data
            
            if unclear_items:
                await _show_next_unclear_item(query, meal_data)
            else:
                await _finalize_meal_logging(query, context, meal_data, chat_id)


async def _show_next_unclear_item(query, meal_data):
    """Show the next unclear item for confirmation"""
    unclear_items = meal_data.get('unclear_items', [])
    items = meal_data.get('items', [])
    meal_type = meal_data.get('meal_type', 'lunch')
    
    meal_emoji = {
        'breakfast': '🌅',
        'lunch': '🌞',
        'dinner': '🌙'
    }
    emoji = meal_emoji.get(meal_type, '🍽️')
    
    message = f"{emoji} **Confirming {meal_type.capitalize()} Items**\n\n"
    
    # Show confirmed items
    if items:
        message += "✅ **Confirmed:**\n"
        for item in items:
            qty = item.get('quantity', 1.0)
            qty_text = f"{qty}× " if qty != 1.0 else ""
            message += f"• {qty_text}{item['name']}\n"
        message += "\n"
    
    message += "❓ **Next item:**\n\n"
    
    next_unclear = unclear_items[0]
    user_mentioned = next_unclear.get('user_mentioned', 'item')
    suggestions = next_unclear.get('suggestions', [])
    qty = next_unclear.get('quantity', 1.0)
    
    qty_text = f"{qty}× " if qty != 1.0 else ""
    message += f"You said: **{qty_text}{user_mentioned}**\n"
    message += "Did you mean:\n"
    
    keyboard = []
    for i, suggestion in enumerate(suggestions[:3]):
        keyboard.append([
            InlineKeyboardButton(
                f"✓ {suggestion}",
                callback_data=f"logmeal_select:{i}:{suggestion[:30]}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton(
            "⏭ Skip this item",
            callback_data="logmeal_skip:0"
        )
    ])
    
    keyboard.append([
        InlineKeyboardButton(
            "❌ Cancel",
            callback_data="logmeal_cancel"
        )
    ])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message, parse_mode='Markdown', reply_markup=reply_markup)


async def _finalize_meal_logging(query, context, meal_data, chat_id):
    """Finalize meal logging after all items are confirmed"""
    items = meal_data.get('items', [])
    meal_type = meal_data.get('meal_type', 'lunch')
    
    # Get user profile
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await query.edit_message_text("❌ User not found. Please use /start first.")
        return
    
    # Now actually log the meal
    @sync_to_async
    def log_confirmed_meal():
        """Log the confirmed meal to database"""
        try:
            from django.utils import timezone as django_tz
            from datetime import date as date_type
            
            today = date_type.today()
            
            # Find or create daily menu
            daily_menu, _ = DailyMenu.objects.get_or_create(
                date=today,
                meal_type=meal_type,
                defaults={}
            )
            
            # Delete any existing meal plan for this user/meal combination
            # This handles both proposed and previously completed meals
            existing_plans = MealPlan.objects.filter(
                user=profile.user,
                daily_menu=daily_menu
            )
            
            if existing_plans.exists():
                plan_action = "updated"
                existing_plans.delete()
            else:
                plan_action = "created"
            
            # Create new completed meal plan
            meal_plan = MealPlan.objects.create(
                user=profile.user,
                daily_menu=daily_menu,
                explanation=f"Actual meal logged (confirmed)",
                status='completed',
                completed_at=django_tz.now()
            )
            
            # Add dishes
            found_dishes = []
            total_nutrition = {
                'calories': 0, 'protein': 0, 'carbs': 0,
                'fat': 0, 'fiber': 0, 'sodium': 0, 'sugars': 0
            }
            
            for item in items:
                dish_name = item.get('name', '').strip()
                quantity = float(item.get('quantity', 1.0))
                
                try:
                    dish = Dish.objects.get(name__iexact=dish_name)
                    
                    MealPlanDish.objects.create(
                        meal_plan=meal_plan,
                        dish=dish,
                        quantity=quantity
                    )
                    
                    MealHistory.objects.create(
                        user=profile.user,
                        dish=dish,
                        daily_menu=daily_menu,
                        meal_plan=meal_plan,
                        quantity=quantity,
                        eaten_at=django_tz.now()
                    )
                    
                    found_dishes.append({
                        'name': dish.name,
                        'quantity': quantity,
                        'calories': dish.calories * quantity
                    })
                    
                    total_nutrition['calories'] += dish.calories * quantity
                    total_nutrition['protein'] += dish.protein * quantity
                    total_nutrition['carbs'] += dish.total_carbohydrate * quantity
                    total_nutrition['fat'] += dish.total_fat * quantity
                    total_nutrition['fiber'] += dish.dietary_fiber * quantity
                    total_nutrition['sodium'] += dish.sodium * quantity
                    total_nutrition['sugars'] += dish.total_sugars * quantity
                    
                except Dish.DoesNotExist:
                    logger.warning(f"Dish '{dish_name}' not found during finalization")
            
            return {
                'success': True,
                'plan_action': plan_action,
                'meal_type': meal_type,
                'found_dishes': found_dishes,
                'total_nutrition': total_nutrition
            }
            
        except Exception as e:
            logger.error(f"Error finalizing meal: {e}")
            return {'success': False, 'error': str(e)}
    
    result = await log_confirmed_meal()
    
    if not result.get('success'):
        await query.edit_message_text(
            f"❌ Error logging meal: {result.get('error', 'Unknown error')}"
        )
        context.user_data.pop('logmeal_data', None)
        return
    
    # Format success message
    meal_emoji = {
        'breakfast': '🌅',
        'lunch': '🌞',
        'dinner': '🌙'
    }
    emoji = meal_emoji.get(result['meal_type'], '🍽️')
    
    message = f"{emoji} **Meal Logged** - {result['meal_type'].capitalize()}\n\n"
    
    if result['plan_action'] == 'updated':
        message += "✅ Updated your proposed meal plan with what you actually ate\n\n"
    else:
        message += "✅ Created new meal record\n\n"
    
    if result['found_dishes']:
        message += "**What you ate:**\n"
        for item in result['found_dishes']:
            qty_text = ""
            if item['quantity'] == 0.5:
                qty_text = "½ "
            elif item['quantity'] != 1.0:
                qty_text = f"{item['quantity']}× "
            
            cal_text = f" ({int(item['calories'])} cal)" if item['calories'] > 0 else ""
            message += f"• {qty_text}{item['name']}{cal_text}\n"
    
    nutrition = result['total_nutrition']
    message += f"\n📊 **Total Nutrition:**\n"
    message += f"Calories: {int(nutrition['calories'])} kcal\n"
    message += f"Protein: {int(nutrition['protein'])}g | "
    message += f"Carbs: {int(nutrition['carbs'])}g | "
    message += f"Fat: {int(nutrition['fat'])}g\n"
    message += f"Fiber: {int(nutrition['fiber'])}g | "
    message += f"Sodium: {int(nutrition['sodium'])}mg | "
    message += f"Sugars: {int(nutrition['sugars'])}g"
    
    await query.edit_message_text(message, parse_mode='Markdown')
    context.user_data.pop('logmeal_data', None)


async def feedback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle feedback messages - uses AI to extract dish ratings"""
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text(
            "❌ Please use /start first to register!"
        )
        return
    
    if not update.message.text:
        await update.message.reply_text(
            "Please provide your feedback in text format."
        )
        return
    
    feedback_text = update.message.text.strip()
    
    # Send acknowledgment (will be edited with result)
    processing_msg = await update.message.reply_text(
        "🤔 Processing your feedback..."
    )
    
    # Process feedback using AI
    @sync_to_async
    def process_feedback():
        """Process feedback using OpenAI to extract dish ratings"""
        try:
            sys.path.insert(0, os.path.join(settings.BASE_DIR, 'huds_lib'))
            from openai import OpenAI
            
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            
            # Get list of available dishes from recent menus (last 7 days)
            from datetime import timedelta
            from django.utils import timezone
            seven_days_ago = timezone.now() - timedelta(days=7)
            
            # Get all dishes from recent daily menus
            recent_dishes = Dish.objects.filter(
                menus__date__gte=seven_days_ago
            ).distinct().values_list('name', flat=True).order_by('name')[:200]  # Limit to avoid token overflow
            
            available_dishes_list = "\n".join([f"- {dish}" for dish in recent_dishes])
            
            # Ask GPT to extract dish names and ratings from the feedback
            prompt = f"""Analyze this user feedback about HUDS dining hall food and extract:
1. Which specific dishes are mentioned
2. A rating from -2 to 2 for each dish:
   -2 = Never again (disgusting/hated it)
   -1 = Bad but edible (don't like)
    0 = Neutral (no strong opinion)
    1 = Good, liked it
    2 = Absolutely love it

IMPORTANT: You MUST use EXACT dish names from this list (case-sensitive):
{available_dishes_list}

User feedback: "{feedback_text}"

Return ONLY a valid JSON object with this structure:
{{
  "dishes": [
    {{"name": "Exact Dish Name From List", "rating": -2, "reason": "brief reason"}},
    {{"name": "Another Exact Dish Name", "rating": 1, "reason": "brief reason"}}
  ],
  "general_preferences": "any dietary preferences mentioned (like 'wants more protein' or 'prefers oatmeal')"
}}

Rules:
- ONLY use exact dish names from the provided list
- If a dish isn't in the list, don't include it in dishes array
- Put general food preferences in "general_preferences" field
- If no specific dishes from the list are mentioned, return empty dishes array"""
            
            # Get the model name from settings or use gpt-5 as default
            model_name = getattr(settings, 'OPENAI_MODEL', 'gpt-5')
            
            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that outputs only valid JSON."},
                    {"role": "user", "content": prompt}
                ]
                # Note: GPT-5 only supports default temperature of 1
            )
            
            result = response.choices[0].message.content
            
            # Extract JSON from response (may have extra text)
            import json
            try:
                data = json.loads(result)
            except json.JSONDecodeError:
                # Try to extract JSON from text
                import re
                json_match = re.search(r'\{[\s\S]*\}', result)
                if json_match:
                    data = json.loads(json_match.group(0))
                else:
                    raise ValueError("Could not extract valid JSON from response")
            
            feedbacks_created = 0
            dishes_saved = []
            dishes_not_found = []
            
            # Store feedback for each dish
            for dish_feedback in data.get('dishes', []):
                dish_name = dish_feedback.get('name', '').strip()
                rating = dish_feedback.get('rating', 0)
                reason = dish_feedback.get('reason', '')
                
                if not dish_name:
                    continue
                
                # Try to find the dish in database (case-insensitive exact match first)
                try:
                    dish = Dish.objects.get(name__iexact=dish_name)
                    
                    # Try to find related meal history for better context
                    meal_history = None
                    try:
                        # Look for recent meal history for this user and dish (last 7 days)
                        from datetime import timedelta
                        from django.utils import timezone
                        seven_days_ago = timezone.now() - timedelta(days=7)

                        meal_history = MealHistory.objects.filter(
                            user=profile.user,
                            dish=dish,
                            eaten_at__gte=seven_days_ago
                        ).order_by('-eaten_at').first()
                    except Exception as e:
                        logger.warning(f"Could not find meal history for feedback: {e}")

                    # Create or update feedback
                    UserFeedback.objects.create(
                        user=profile.user,
                        dish=dish,
                        meal_history=meal_history,
                        rating=rating,
                        comment=reason
                    )
                    feedbacks_created += 1
                    dishes_saved.append(dish.name)
                    logger.info(f"Created feedback: {dish.name} = {rating} ({reason})")
                    
                except Dish.DoesNotExist:
                    # Try fuzzy matching (contains)
                    similar_dishes = Dish.objects.filter(name__icontains=dish_name)[:3]
                    if similar_dishes.count() > 0:
                        # Found similar dishes
                        similar_names = [d.name for d in similar_dishes]
                        dishes_not_found.append({
                            'attempted': dish_name,
                            'suggestions': similar_names
                        })
                        logger.warning(f"Dish '{dish_name}' not found exactly. Similar: {similar_names}")
                    else:
                        dishes_not_found.append({
                            'attempted': dish_name,
                            'suggestions': []
                        })
                        logger.warning(f"Dish '{dish_name}' not found in database for feedback")
            
            # Update dietary preferences if mentioned
            general_prefs = data.get('general_preferences', '').strip()
            prefs_updated = False
            if general_prefs:
                current_prefs = profile.dietary_restrictions or ''
                if general_prefs not in current_prefs:
                    if current_prefs:
                        profile.dietary_restrictions = f"{current_prefs}. {general_prefs}".strip()
                    else:
                        profile.dietary_restrictions = general_prefs
                    profile.save()
                    prefs_updated = True
                    logger.info(f"Updated dietary preferences: {general_prefs}")
            
            return {
                'feedbacks_created': feedbacks_created,
                'dishes_saved': dishes_saved,
                'dishes_not_found': dishes_not_found,
                'general_preferences': general_prefs,
                'prefs_updated': prefs_updated
            }
            
        except Exception as e:
            logger.error(f"Error processing feedback: {e}")
            return {'error': str(e)}
    
    result = await process_feedback()
    
    if 'error' in result:
        await processing_msg.edit_text(
            f"❌ Sorry, I had trouble processing your feedback:\n{result['error']}\n\n"
            "Please try again or contact support."
        )
    else:
        feedbacks_created = result.get('feedbacks_created', 0)
        dishes_saved = result.get('dishes_saved', [])
        dishes_not_found = result.get('dishes_not_found', [])
        prefs_updated = result.get('prefs_updated', False)
        general_prefs = result.get('general_preferences', '')
        
        message = ""
        
        if feedbacks_created > 0:
            dishes_text = '\n• '.join(dishes_saved)
            message = f"✅ Saved your feedback about:\n• {dishes_text}"
            if prefs_updated and general_prefs:
                message += f"\n\n📝 Added preference: {general_prefs}"
            
        if dishes_not_found:
            if message:
                message += "\n\n"
            message += "⚠️ Couldn't find:\n"
            for item in dishes_not_found:
                message += f"• {item['attempted']}\n"
                if item['suggestions']:
                    suggestions_text = ', '.join(item['suggestions'][:2])
                    message += f"  Maybe: {suggestions_text}?\n"
            
        if not message:
            if prefs_updated and general_prefs:
                message = f"✅ Added preference:\n• {general_prefs}\n\nUse /nextmeal to generate a new plan!"
            else:
                message = "✅ Noted your feedback!"
        
        await processing_msg.edit_text(message)


async def meal_plan_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Accept/Modify button callbacks"""
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    action, meal_plan_id = callback_data.split('_', 1)
    meal_plan_id = int(meal_plan_id)
    
    chat_id = update.effective_chat.id
    
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await query.edit_message_text("❌ Please use /start first to register!")
        return
    
    @sync_to_async
    def get_meal_plan():
        try:
            return MealPlan.objects.get(id=meal_plan_id, user=profile.user)
        except MealPlan.DoesNotExist:
            return None
    
    meal_plan = await get_meal_plan()
    
    if not meal_plan:
        await query.edit_message_text("❌ Meal plan not found.")
        return
    
    if action == 'accept':
        # Accept the meal plan
        @sync_to_async
        def accept_plan():
            # Use the model's approve method which sets status to 'approved' and records timestamp
            meal_plan.approve()

            # Add dishes to meal history
            for plan_dish in meal_plan.mealplandish_set.all():
                MealHistory.objects.create(
                    user=profile.user,
                    dish=plan_dish.dish,
                    daily_menu=meal_plan.daily_menu,
                    quantity=plan_dish.quantity
                )

        await accept_plan()

        # Update the message to remove buttons
        await query.edit_message_text(
            query.message.text + "\n\n✅ **Meal plan approved!** Added to your meal history.",
            parse_mode='Markdown'
        )
        
    elif action == 'modify':
        # Delete the rejected meal plan
        @sync_to_async
        def delete_plan():
            # MealPlanDish entries will be deleted automatically via CASCADE
            meal_plan.delete()
        
        await delete_plan()
        
        # Request modification
        await query.edit_message_text(
            query.message.text + "\n\n🔄 **Meal plan rejected and removed.**\n\n"
            "Please provide feedback on what you'd like to change:\n"
            "Reply with your preferences (e.g., 'no strawberries', 'more protein', etc.)\n\n"
            "Then use /nextmeal again to generate a new plan with your updated preferences.",
            parse_mode='Markdown'
        )


async def fetch_date_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle date selection callback for /fetch command"""
    query = update.callback_query
    await query.answer()
    
    chat_id = update.effective_chat.id
    
    # Check if user is admin
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await query.edit_message_text("❌ Please use /start first to register!")
        return
    
    if not profile.is_admin:
        await query.edit_message_text("❌ This command is only available to admins.")
        return
    
    # Parse the date from callback data
    from datetime import date as date_type
    callback_data = query.data
    
    if not callback_data.startswith('fetch_date:'):
        await query.edit_message_text("❌ Invalid callback data")
        return
    
    date_str = callback_data.replace('fetch_date:', '')
    try:
        fetch_date = date_type.fromisoformat(date_str)
    except ValueError:
        await query.edit_message_text("❌ Invalid date format")
        return
    
    # Edit the message to show fetch is starting
    await query.edit_message_text(
        f"🔄 Fetching menus for {fetch_date.strftime('%A, %B %d, %Y')}..."
    )
    
    # Execute the fetch using the query.message
    await _execute_fetch_for_callback(query, fetch_date)


async def _execute_fetch_for_callback(query, fetch_date):
    """Execute the menu fetch for a callback query"""
    import sys
    import os
    
    try:
        # Import and run the fetch task
        sys.path.insert(0, os.path.join(settings.BASE_DIR, 'menu'))
        from menu.tasks import fetch_tomorrow_menus
        
        @sync_to_async
        def run_fetch_task():
            # Call the Celery task synchronously for admin command
            return fetch_tomorrow_menus(target_date=fetch_date)
        
        result = await run_fetch_task()
        
        if result.get('status') == 'success':
            stats = result.get('stats', {})
            message = (
                f"✅ Successfully fetched menus for {fetch_date.strftime('%A, %B %d, %Y')}\n\n"
                f"📊 Stats:\n"
                f"• Breakfast: {stats.get('breakfast', 0)} dishes\n"
                f"• Lunch: {stats.get('lunch', 0)} dishes\n"
                f"• Dinner: {stats.get('dinner', 0)} dishes\n"
                f"• Total: {stats.get('total', 0)} dishes"
            )
        else:
            message = f"⚠️ Fetch completed with warnings:\n{result.get('message', 'Unknown status')}"
        
        await query.edit_message_text(message)
        
    except Exception as e:
        logger.error(f"Error in fetch date callback: {e}")
        await query.edit_message_text(
            f"❌ Error fetching menus:\n{str(e)}"
        )


async def fetch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fetch command - admin only, manually fetch menus"""
    chat_id = update.effective_chat.id
    
    # Check if user is admin
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text("❌ Please use /start first to register!")
        return
    
    if not profile.is_admin:
        await update.message.reply_text("❌ This command is only available to admins.")
        return
    
    # Parse date argument or show date picker
    from datetime import date, timedelta
    import sys
    import os
    
    if context.args:
        # Try to parse date from args (format: YYYY-MM-DD or MM/DD/YYYY)
        date_str = context.args[0]
        try:
            # Try YYYY-MM-DD format
            if '-' in date_str:
                year, month, day = date_str.split('-')
                fetch_date = date(int(year), int(month), int(day))
            # Try MM/DD/YYYY format
            elif '/' in date_str:
                month, day, year = date_str.split('/')
                fetch_date = date(int(year), int(month), int(day))
            else:
                await update.message.reply_text(
                    "❌ Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY\n"
                    "Example: `/fetch 2025-09-30` or `/fetch 9/30/2025`"
                )
                return
        except (ValueError, IndexError):
            await update.message.reply_text(
                "❌ Invalid date format. Use YYYY-MM-DD or MM/DD/YYYY\n"
                "Example: `/fetch 2025-09-30` or `/fetch 9/30/2025`"
            )
            return
    else:
        # Show interactive date picker
        today = date.today()
        keyboard = []
        
        # Create buttons for the next 7 days
        for i in range(7):
            target_date = today + timedelta(days=i)
            if i == 0:
                label = f"📅 Today ({target_date.strftime('%m/%d')})"
            elif i == 1:
                label = f"📅 Tomorrow ({target_date.strftime('%m/%d')})"
            else:
                label = f"📅 {target_date.strftime('%A, %m/%d')}"
            
            keyboard.append([
                InlineKeyboardButton(label, callback_data=f"fetch_date:{target_date.isoformat()}")
            ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📅 Select a date to fetch menus:\n\n"
            "Or use: `/fetch YYYY-MM-DD` for a specific date",
            reply_markup=reply_markup
        )
        return
    
    # Proceed with fetch if date was provided
    await _execute_fetch(update.message, fetch_date)


async def _execute_fetch(message, fetch_date):
    """Execute the menu fetch for a specific date"""
    from datetime import date, timedelta
    import sys
    import os
    
    status_msg = await message.reply_text(
        f"🔄 Fetching menus for {fetch_date}..."
    )
    
    try:
        # Import and run the fetch task
        sys.path.insert(0, os.path.join(settings.BASE_DIR, 'menu'))
        from menu.tasks import fetch_tomorrow_menus
        
        @sync_to_async
        def run_fetch_task():
            # Call the Celery task synchronously for admin command
            return fetch_tomorrow_menus(target_date=fetch_date)
        
        result = await run_fetch_task()
        
        if result.get('status') == 'success':
            stats = result.get('stats', {})
            message = (
                f"✅ Successfully fetched menus for {fetch_date}\n\n"
                f"📊 Stats:\n"
                f"• Breakfast: {stats.get('breakfast', 0)} dishes\n"
                f"• Lunch: {stats.get('lunch', 0)} dishes\n"
                f"• Dinner: {stats.get('dinner', 0)} dishes\n"
                f"• Total: {stats.get('total', 0)} dishes"
            )
        else:
            message = f"⚠️ Fetch completed with warnings:\n{result.get('message', 'Unknown status')}"
        
        await status_msg.edit_text(message)
        
    except Exception as e:
        logger.error(f"Error in /fetch command: {e}")
        await status_msg.edit_text(
            f"❌ Error fetching menus:\n{str(e)}"
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command - admin only, show system statistics"""
    chat_id = update.effective_chat.id
    
    # Check if user is admin
    try:
        profile = await sync_to_async(UserProfile.objects.get)(telegram_chat_id=chat_id)
    except UserProfile.DoesNotExist:
        await update.message.reply_text("❌ Please use /start first to register!")
        return
    
    if not profile.is_admin:
        await update.message.reply_text("❌ This command is only available to admins.")
        return
    
    @sync_to_async
    def get_stats():
        from datetime import date, timedelta
        
        # Get counts
        total_users = UserProfile.objects.count()
        active_users = UserProfile.objects.filter(notifications_enabled=True).count()
        total_dishes = Dish.objects.count()
        
        # Get recent menu count
        today = date.today()
        week_ago = today - timedelta(days=7)
        recent_menus = DailyMenu.objects.filter(date__gte=week_ago).count()
        
        # Get meal plans generated
        total_meal_plans = MealPlan.objects.count()
        recent_meal_plans = MealPlan.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # Get feedback count
        total_feedback = UserFeedback.objects.count()
        
        return {
            'total_users': total_users,
            'active_users': active_users,
            'total_dishes': total_dishes,
            'recent_menus': recent_menus,
            'total_meal_plans': total_meal_plans,
            'recent_meal_plans': recent_meal_plans,
            'total_feedback': total_feedback
        }
    
    stats = await get_stats()
    
    message = (
        "📊 **System Statistics**\n\n"
        f"👥 Users: {stats['total_users']} ({stats['active_users']} active)\n"
        f"🍽️ Total Dishes: {stats['total_dishes']}\n"
        f"📅 Menus (Last 7 days): {stats['recent_menus']}\n"
        f"🎯 Meal Plans Generated:\n"
        f"   • Total: {stats['total_meal_plans']}\n"
        f"   • Last 7 days: {stats['recent_meal_plans']}\n"
        f"💬 Total Feedback: {stats['total_feedback']}"
    )
    
    await update.message.reply_text(message, parse_mode='Markdown')


def format_meal_plan(meal_plan):
    """Format a meal plan for display (synchronous version) - with full nutrition table"""
    try:
        # Access all related objects in the sync context
        daily_menu = meal_plan.daily_menu
        meal_type_display = daily_menu.get_meal_type_display()
        menu_date = daily_menu.date
        explanation = meal_plan.explanation
        
        # Get dishes if they exist
        dishes_with_qty = []
        try:
            dishes_with_qty = list(meal_plan.mealplandish_set.all().select_related('dish'))
        except:
            pass
        
        plan_data = {
            'meal_type_display': meal_type_display,
            'menu_date': menu_date,
            'explanation': explanation,
            'dishes': dishes_with_qty
        }
    except Exception as e:
        # Fallback if there's an error
        plan_data = {
            'meal_type_display': 'Meal',
            'menu_date': 'Unknown',
            'explanation': '',
            'dishes': []
        }
    
    # Map meal types to emojis
    meal_emoji = {
        'Breakfast': '🌅',
        'Lunch': '🌞',
        'Dinner': '🌙'
    }
    emoji = meal_emoji.get(plan_data['meal_type_display'], '🍽️')
    
    message = f"{emoji} **{plan_data['meal_type_display']}** - {plan_data['menu_date']}\n\n"
    
    # Show dishes
    if plan_data['dishes']:
        # Calculate totals
        total_nutrition = {
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'fiber': 0,
            'sodium': 0,
            'sugars': 0
        }
        
        for item in plan_data['dishes']:
            # More descriptive quantity formatting
            if item.quantity == 1.0:
                qty_text = ""
            elif item.quantity == 0.5:
                qty_text = "½ "
            elif item.quantity == 1.5:
                qty_text = "1½ "
            else:
                qty_text = f"{item.quantity}× "

            cals = int(item.dish.calories * item.quantity) if item.dish.calories > 0 else 0
            if cals > 0:
                message += f"• {qty_text}{item.dish.name} ({cals} cal)\n"
            else:
                message += f"• {qty_text}{item.dish.name}\n"
            
            # Add to totals
            total_nutrition['calories'] += item.dish.calories * item.quantity
            total_nutrition['protein'] += item.dish.protein * item.quantity
            total_nutrition['carbs'] += item.dish.total_carbohydrate * item.quantity
            total_nutrition['fat'] += item.dish.total_fat * item.quantity
            total_nutrition['fiber'] += item.dish.dietary_fiber * item.quantity
            total_nutrition['sodium'] += item.dish.sodium * item.quantity
            total_nutrition['sugars'] += item.dish.total_sugars * item.quantity
        
        # Add nutritional breakdown table
        message += f"\n📊 **Nutrition:**\n"
        message += f"Calories: {int(total_nutrition['calories'])} kcal\n"
        message += f"Protein: {int(total_nutrition['protein'])}g | "
        message += f"Carbs: {int(total_nutrition['carbs'])}g | "
        message += f"Fat: {int(total_nutrition['fat'])}g\n"
        message += f"Fiber: {int(total_nutrition['fiber'])}g | "
        message += f"Sodium: {int(total_nutrition['sodium'])}mg | "
        message += f"Sugars: {int(total_nutrition['sugars'])}g\n"
        
        # Add portion note
        message += f"\nℹ️ Note: 1 scoop = 1 portion\n"
        
        # Add AI suggestions if available
        if plan_data['explanation']:
            message += f"\n💡 **Tips:**\n{plan_data['explanation']}"
    
    return message


async def format_meal_plan_async(meal_plan):
    """Format a meal plan for display (async version) - with full nutrition table"""
    @sync_to_async
    def get_plan_data():
        """Get all needed data from the meal plan in one sync call"""
        try:
            # Access all related objects in the sync context
            daily_menu = meal_plan.daily_menu
            meal_type_display = daily_menu.get_meal_type_display()
            menu_date = daily_menu.date
            explanation = meal_plan.explanation
            
            # Get dishes if they exist
            dishes_with_qty = []
            try:
                dishes_with_qty = list(meal_plan.mealplandish_set.all().select_related('dish'))
            except:
                pass
            
            return {
                'meal_type_display': meal_type_display,
                'menu_date': menu_date,
                'explanation': explanation,
                'dishes': dishes_with_qty
            }
        except Exception as e:
            # Fallback if there's an error
            return {
                'meal_type_display': 'Meal',
                'menu_date': 'Unknown',
                'explanation': '',
                'dishes': []
            }
    
    plan_data = await get_plan_data()
    
    # Map meal types to emojis
    meal_emoji = {
        'Breakfast': '🌅',
        'Lunch': '🌞',
        'Dinner': '🌙'
    }
    emoji = meal_emoji.get(plan_data['meal_type_display'], '🍽️')
    
    message = f"{emoji} **{plan_data['meal_type_display']}** - {plan_data['menu_date']}\n\n"
    
    # Show dishes
    if plan_data['dishes']:
        # Calculate totals
        total_nutrition = {
            'calories': 0,
            'protein': 0,
            'carbs': 0,
            'fat': 0,
            'fiber': 0,
            'sodium': 0,
            'sugars': 0
        }
        
        for item in plan_data['dishes']:
            # More descriptive quantity formatting
            if item.quantity == 1.0:
                qty_text = ""
            elif item.quantity == 0.5:
                qty_text = "½ "
            elif item.quantity == 1.5:
                qty_text = "1½ "
            else:
                qty_text = f"{item.quantity}× "

            cals = int(item.dish.calories * item.quantity) if item.dish.calories > 0 else 0
            if cals > 0:
                message += f"• {qty_text}{item.dish.name} ({cals} cal)\n"
            else:
                message += f"• {qty_text}{item.dish.name}\n"
            
            # Add to totals
            total_nutrition['calories'] += item.dish.calories * item.quantity
            total_nutrition['protein'] += item.dish.protein * item.quantity
            total_nutrition['carbs'] += item.dish.total_carbohydrate * item.quantity
            total_nutrition['fat'] += item.dish.total_fat * item.quantity
            total_nutrition['fiber'] += item.dish.dietary_fiber * item.quantity
            total_nutrition['sodium'] += item.dish.sodium * item.quantity
            total_nutrition['sugars'] += item.dish.total_sugars * item.quantity
        
        # Add nutritional breakdown table
        message += f"\n📊 **Nutrition:**\n"
        message += f"Calories: {int(total_nutrition['calories'])} kcal\n"
        message += f"Protein: {int(total_nutrition['protein'])}g | "
        message += f"Carbs: {int(total_nutrition['carbs'])}g | "
        message += f"Fat: {int(total_nutrition['fat'])}g\n"
        message += f"Fiber: {int(total_nutrition['fiber'])}g | "
        message += f"Sodium: {int(total_nutrition['sodium'])}mg | "
        message += f"Sugars: {int(total_nutrition['sugars'])}g\n"
        
        # Add portion note
        message += f"\nℹ️ Note: 1 scoop = 1 portion\n"
        
        # Add AI suggestions if available
        if plan_data['explanation']:
            message += f"\n💡 **Tips:**\n{plan_data['explanation']}"
    
    return message
