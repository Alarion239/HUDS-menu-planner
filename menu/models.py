"""
Models for the menu app - managing dishes and daily menus.
"""
from django.db import models
from django.utils import timezone


class Dish(models.Model):
    """
    Represents a dish with its nutritional information.
    All nutritional fields are stored as floats, with 0.0 for missing data.
    """
    # Basic information
    name = models.CharField(max_length=255, unique=True, db_index=True)
    portion_size = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)  # e.g., "Entrees", "Sides"
    detail_url = models.URLField(max_length=500, blank=True)
    
    # Nutritional data (all as floats, 0.0 for missing)
    calories = models.FloatField(default=0.0)
    serving_size = models.CharField(max_length=100, blank=True)
    
    # Macronutrients (in grams)
    total_fat = models.FloatField(default=0.0, help_text="Total fat in grams")
    saturated_fat = models.FloatField(default=0.0, help_text="Saturated fat in grams")
    trans_fat = models.FloatField(default=0.0, help_text="Trans fat in grams")
    cholesterol = models.FloatField(default=0.0, help_text="Cholesterol in milligrams")
    sodium = models.FloatField(default=0.0, help_text="Sodium in milligrams")
    total_carbohydrate = models.FloatField(default=0.0, help_text="Total carbohydrate in grams")
    dietary_fiber = models.FloatField(default=0.0, help_text="Dietary fiber in grams")
    total_sugars = models.FloatField(default=0.0, help_text="Total sugars in grams")
    added_sugars = models.FloatField(default=0.0, help_text="Added sugars in grams")
    protein = models.FloatField(default=0.0, help_text="Protein in grams")
    
    # Vitamins and minerals
    vitamin_d = models.FloatField(default=0.0, help_text="Vitamin D in micrograms")
    calcium = models.FloatField(default=0.0, help_text="Calcium in milligrams")
    iron = models.FloatField(default=0.0, help_text="Iron in milligrams")
    potassium = models.FloatField(default=0.0, help_text="Potassium in milligrams")
    
    # Ingredients and allergens
    ingredients = models.TextField(blank=True, help_text="Comma-separated ingredients")
    
    # Metadata
    first_seen = models.DateField(auto_now_add=True, help_text="When this dish was first added")
    last_seen = models.DateField(auto_now=True, help_text="When this dish was last on a menu")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Dishes"
    
    def __str__(self):
        return self.name
    
    def get_ingredients_list(self):
        """Return ingredients as a list"""
        if not self.ingredients:
            return []
        return [ing.strip() for ing in self.ingredients.split(',')]


class DailyMenu(models.Model):
    """
    Represents a menu for a specific date and meal type.
    Links to the dishes available on that menu.
    """
    MEAL_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
    ]
    
    date = models.DateField(db_index=True)
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES, db_index=True)
    dishes = models.ManyToManyField(Dish, related_name='menus', blank=True)
    
    # Metadata
    fetched_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date', 'meal_type']
        unique_together = ['date', 'meal_type']
        verbose_name_plural = "Daily Menus"
    
    def __str__(self):
        return f"{self.get_meal_type_display()} - {self.date}"
    
    def get_dishes_by_category(self):
        """Return dishes grouped by category"""
        categories = {}
        for dish in self.dishes.all().order_by('category', 'name'):
            category = dish.category or 'Other'
            if category not in categories:
                categories[category] = []
            categories[category].append(dish)
        return categories