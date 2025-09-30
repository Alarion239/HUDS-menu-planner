"""
Admin configuration for users app models.
"""
from django.contrib import admin
from .models import UserProfile, MealPlan, MealPlanDish, MealHistory, UserFeedback


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'telegram_username', 'telegram_chat_id', 'is_admin', 'notifications_enabled', 'created_at']
    list_filter = ['is_admin', 'notifications_enabled', 'breakfast_notification', 'lunch_notification', 'dinner_notification']
    search_fields = ['user__username', 'telegram_username', 'telegram_chat_id']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'telegram_chat_id', 'telegram_username', 'is_admin')
        }),
        ('Nutritional Goals', {
            'fields': (
                'target_calories',
                ('target_protein', 'target_carbs', 'target_fat'),
                ('target_fiber', 'max_sodium', 'max_added_sugars'),
            )
        }),
        ('Dietary Preferences', {
            'fields': ('dietary_restrictions', 'food_preferences')
        }),
        ('Notification Settings', {
            'fields': (
                'notifications_enabled',
                ('breakfast_notification', 'lunch_notification', 'dinner_notification'),
            )
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


class MealPlanDishInline(admin.TabularInline):
    model = MealPlanDish
    extra = 1


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ['user', 'daily_menu', 'status', 'created_at', 'sent_at', 'approved_at']
    list_filter = ['status', 'daily_menu__meal_type', 'created_at']
    search_fields = ['user__username', 'explanation']
    readonly_fields = ['created_at', 'sent_at', 'approved_at', 'completed_at']
    inlines = [MealPlanDishInline]
    
    fieldsets = (
        ('Plan Information', {
            'fields': ('user', 'daily_menu', 'status', 'explanation')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'sent_at', 'approved_at', 'completed_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(MealHistory)
class MealHistoryAdmin(admin.ModelAdmin):
    list_display = ['user', 'dish', 'quantity', 'eaten_at', 'daily_menu']
    list_filter = ['eaten_at', 'daily_menu__meal_type']
    search_fields = ['user__username', 'dish__name']
    date_hierarchy = 'eaten_at'
    readonly_fields = ['created_at']


@admin.register(UserFeedback)
class UserFeedbackAdmin(admin.ModelAdmin):
    list_display = ['user', 'dish', 'rating', 'get_rating_display', 'feedback_date']
    list_filter = ['rating', 'feedback_date']
    search_fields = ['user__username', 'dish__name', 'comment']
    date_hierarchy = 'feedback_date'
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Feedback Information', {
            'fields': ('user', 'dish', 'meal_history', 'rating', 'comment')
        }),
        ('Metadata', {
            'fields': ('feedback_date', 'created_at'),
            'classes': ('collapse',)
        }),
    )