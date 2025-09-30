"""
Management command to fetch daily menus from HUDS website.
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from datetime import date, timedelta
import sys
import os

# Add huds_lib to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..', 'huds_lib'))

from huds_lib.webpage import harvard_dining_menu_url
from huds_lib.parser import harvard_detailed_menu_retrieve
from menu.models import Dish, DailyMenu


class Command(BaseCommand):
    help = 'Fetch daily menu from HUDS website and store in database'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Date to fetch (YYYY-MM-DD), defaults to tomorrow',
        )
        parser.add_argument(
            '--meals',
            nargs='+',
            choices=['breakfast', 'lunch', 'dinner'],
            default=['breakfast', 'lunch', 'dinner'],
            help='Which meals to fetch (default: all)',
        )

    def handle(self, *args, **options):
        # Parse date
        if options['date']:
            try:
                target_date = date.fromisoformat(options['date'])
            except ValueError:
                raise CommandError(f'Invalid date format: {options["date"]}. Use YYYY-MM-DD')
        else:
            # Default to tomorrow
            target_date = date.today() + timedelta(days=1)

        self.stdout.write(f'Fetching menus for {target_date}...')

        # Fetch each meal
        for meal_type in options['meals']:
            self.stdout.write(f'\n{"="*60}')
            self.stdout.write(f'Fetching {meal_type.upper()} menu...')
            self.stdout.write(f'{"="*60}')
            
            try:
                # Generate URL
                url = harvard_dining_menu_url(target_date, meal_type.capitalize())
                self.stdout.write(f'URL: {url}')
                
                # Fetch detailed menu
                menu_data = harvard_detailed_menu_retrieve(url, quiet=False)
                
                if 'error' in menu_data:
                    self.stdout.write(self.style.ERROR(f'Error: {menu_data["error"]}'))
                    continue
                
                # Get or create DailyMenu
                daily_menu, created = DailyMenu.objects.get_or_create(
                    date=target_date,
                    meal_type=meal_type.lower()
                )
                
                if created:
                    self.stdout.write(self.style.SUCCESS(f'Created new DailyMenu: {daily_menu}'))
                else:
                    self.stdout.write(self.style.WARNING(f'Updating existing DailyMenu: {daily_menu}'))
                    # Clear existing dishes
                    daily_menu.dishes.clear()
                
                # Process dishes
                dishes_added = 0
                dishes_updated = 0
                
                for category_name, items in menu_data.get('menu', {}).items():
                    self.stdout.write(f'\nCategory: {category_name} ({len(items)} items)')
                    
                    for item in items:
                        dish_name = item.get('name', '').strip()
                        if not dish_name:
                            continue
                        
                        # Get or create dish
                        dish, dish_created = Dish.objects.get_or_create(
                            name=dish_name,
                            defaults={
                                'category': category_name,
                                'portion_size': item.get('portion', ''),
                                'detail_url': item.get('detail_url', ''),
                            }
                        )
                        
                        # Update nutrition data if available
                        nutrition = item.get('nutrition', {})
                        if nutrition and item.get('nutrition_fetch_status') == 'success':
                            dish.serving_size = nutrition.get('serving_size', '')
                            dish.calories = self._parse_numeric(nutrition.get('calories', 0))
                            
                            # Parse ingredients
                            ingredients = nutrition.get('ingredients', [])
                            if isinstance(ingredients, list):
                                dish.ingredients = ', '.join(ingredients)
                            
                            # Parse nutrition facts
                            nutrition_facts = nutrition.get('nutrition', {})
                            if nutrition_facts:
                                dish.total_fat = self._parse_nutrition_amount(nutrition_facts.get('Total Fat', {}))
                                dish.saturated_fat = self._parse_nutrition_amount(nutrition_facts.get('Saturated Fat', {}))
                                dish.trans_fat = self._parse_nutrition_amount(nutrition_facts.get('Trans Fat', {}))
                                dish.cholesterol = self._parse_nutrition_amount(nutrition_facts.get('Cholesterol', {}))
                                dish.sodium = self._parse_nutrition_amount(nutrition_facts.get('Sodium', {}))
                                dish.total_carbohydrate = self._parse_nutrition_amount(nutrition_facts.get('Total Carbohydrate', {}))
                                dish.dietary_fiber = self._parse_nutrition_amount(nutrition_facts.get('Dietary Fiber', {}))
                                dish.total_sugars = self._parse_nutrition_amount(nutrition_facts.get('Total Sugars', {}))
                                dish.added_sugars = self._parse_nutrition_amount(nutrition_facts.get('Added Sugars', {}))
                                dish.protein = self._parse_nutrition_amount(nutrition_facts.get('Protein', {}))
                                dish.vitamin_d = self._parse_nutrition_amount(nutrition_facts.get('Vitamin D', {}))
                                dish.calcium = self._parse_nutrition_amount(nutrition_facts.get('Calcium', {}))
                                dish.iron = self._parse_nutrition_amount(nutrition_facts.get('Iron', {}))
                                dish.potassium = self._parse_nutrition_amount(nutrition_facts.get('Potassium', {}))
                            
                            dish.save()
                            
                            if dish_created:
                                dishes_added += 1
                                self.stdout.write(f'  ✓ Added: {dish_name}')
                            else:
                                dishes_updated += 1
                                self.stdout.write(f'  ↻ Updated: {dish_name}')
                        else:
                            if dish_created:
                                dishes_added += 1
                                self.stdout.write(f'  ✓ Added (no nutrition): {dish_name}')
                            else:
                                self.stdout.write(f'  - Exists: {dish_name}')
                        
                        # Add dish to daily menu
                        daily_menu.dishes.add(dish)
                
                self.stdout.write(self.style.SUCCESS(
                    f'\n{meal_type.upper()} Summary:\n'
                    f'  - Dishes added: {dishes_added}\n'
                    f'  - Dishes updated: {dishes_updated}\n'
                    f'  - Total dishes on menu: {daily_menu.dishes.count()}'
                ))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error fetching {meal_type}: {str(e)}'))
                import traceback
                traceback.print_exc()
                continue
        
        self.stdout.write(self.style.SUCCESS('\n✅ Menu fetching completed!'))

    def _parse_numeric(self, value):
        """Parse a numeric value, defaulting to 0.0"""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _parse_nutrition_amount(self, nutrition_dict):
        """Parse nutrition amount from dict with 'amount' key"""
        if not nutrition_dict or not isinstance(nutrition_dict, dict):
            return 0.0
        
        amount_str = nutrition_dict.get('amount', '0')
        if not amount_str:
            return 0.0
        
        # Extract numeric part (e.g., "10g" -> 10, "70mg" -> 70)
        import re
        match = re.match(r'([\d.]+)', str(amount_str))
        if match:
            try:
                value = float(match.group(1))
                # Convert mg to same units if needed (most values are in mg or g)
                # For now, just return the numeric value
                return value
            except ValueError:
                return 0.0
        return 0.0
