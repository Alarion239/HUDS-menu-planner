"""
Admin configuration for menu app models.
"""
from django.contrib import admin
from .models import Dish, DailyMenu


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ['name', 'category', 'calories', 'protein', 'total_carbohydrate', 'total_fat', 'first_seen', 'last_seen']
    list_filter = ['category', 'first_seen', 'last_seen']
    search_fields = ['name', 'ingredients']
    readonly_fields = ['created_at', 'updated_at', 'first_seen', 'last_seen']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'category', 'portion_size', 'serving_size', 'detail_url')
        }),
        ('Nutritional Data', {
            'fields': (
                'calories',
                ('total_fat', 'saturated_fat', 'trans_fat'),
                ('cholesterol', 'sodium'),
                ('total_carbohydrate', 'dietary_fiber'),
                ('total_sugars', 'added_sugars'),
                'protein',
            )
        }),
        ('Vitamins & Minerals', {
            'fields': ('vitamin_d', 'calcium', 'iron', 'potassium'),
            'classes': ('collapse',)
        }),
        ('Ingredients', {
            'fields': ('ingredients',)
        }),
        ('Metadata', {
            'fields': ('first_seen', 'last_seen', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(DailyMenu)
class DailyMenuAdmin(admin.ModelAdmin):
    list_display = ['date', 'meal_type', 'dish_count', 'fetched_at']
    list_filter = ['meal_type', 'date']
    date_hierarchy = 'date'
    filter_horizontal = ['dishes']
    readonly_fields = ['fetched_at', 'updated_at']
    
    def dish_count(self, obj):
        return obj.dishes.count()
    dish_count.short_description = 'Number of Dishes'