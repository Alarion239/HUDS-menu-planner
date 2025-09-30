"""
Models for the users app - managing user profiles, meal history, and feedback.
"""
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from menu.models import Dish, DailyMenu


class UserProfile(models.Model):
    """
    Extended user profile with nutritional goals and preferences.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    telegram_chat_id = models.BigIntegerField(unique=True, null=True, blank=True, db_index=True)
    telegram_username = models.CharField(max_length=255, blank=True)
    
    # Nutritional goals (daily targets)
    target_calories = models.FloatField(default=2000.0, help_text="Target daily calories")
    target_protein = models.FloatField(default=50.0, help_text="Target protein in grams")
    target_carbs = models.FloatField(default=250.0, help_text="Target carbs in grams")
    target_fat = models.FloatField(default=70.0, help_text="Target fat in grams")
    target_fiber = models.FloatField(default=25.0, help_text="Target fiber in grams")
    max_sodium = models.FloatField(default=2300.0, help_text="Max sodium in mg")
    max_added_sugars = models.FloatField(default=50.0, help_text="Max added sugars in grams")
    
    # Dietary preferences and restrictions (free-form text)
    dietary_restrictions = models.TextField(
        blank=True,
        help_text="Dietary restrictions (e.g., 'vegetarian', 'gluten-free', 'no pork')"
    )
    food_preferences = models.TextField(
        blank=True,
        help_text="Food preferences and dislikes"
    )
    
    # Notification preferences
    notifications_enabled = models.BooleanField(default=True)
    breakfast_notification = models.BooleanField(default=True)
    lunch_notification = models.BooleanField(default=True)
    dinner_notification = models.BooleanField(default=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['user__username']
    
    def __str__(self):
        return f"Profile for {self.user.username}"
    
    def get_preferences_text(self):
        """Combine dietary restrictions and preferences for AI prompts"""
        parts = []
        if self.dietary_restrictions:
            parts.append(f"Dietary restrictions: {self.dietary_restrictions}")
        if self.food_preferences:
            parts.append(f"Food preferences: {self.food_preferences}")
        if not parts:
            return "No specific preferences"
        return ". ".join(parts)

    def get_feedback_summary(self, include_weighted_ratings=False):
        """Get a summary of user feedback for AI prompts

        Args:
            include_weighted_ratings (bool): Whether to include weighted ratings in the summary
        """
        from django.utils import timezone
        from datetime import timedelta

        # Get recent feedback (last 30 days) for this user
        thirty_days_ago = timezone.now() - timedelta(days=30)
        feedback = UserFeedback.objects.filter(
            user=self.user,
            feedback_date__gte=thirty_days_ago
        ).select_related('dish').order_by('-feedback_date')

        if not feedback:
            return ""

        # Group feedback by rating with weighted ratings if requested
        loved_items = []
        liked_items = []
        disliked_items = []
        hated_items = []

        for fb in feedback:
            weighted_rating = fb.get_weighted_rating()
            item_name = fb.dish.name

            if include_weighted_ratings:
                # Include weighted rating for more nuanced feedback
                if fb.rating == 2:
                    loved_items.append(f"{item_name} ({weighted_rating:.1f})")
                elif fb.rating == 1:
                    liked_items.append(f"{item_name} ({weighted_rating:.1f})")
                elif fb.rating == -1:
                    disliked_items.append(f"{item_name} ({weighted_rating:.1f})")
                elif fb.rating == -2:
                    hated_items.append(f"{item_name} ({weighted_rating:.1f})")
            else:
                # Simple grouping without weights
                if fb.rating == 2:
                    loved_items.append(item_name)
                elif fb.rating == 1:
                    liked_items.append(item_name)
                elif fb.rating == -1:
                    disliked_items.append(item_name)
                elif fb.rating == -2:
                    hated_items.append(item_name)

        parts = []

        if loved_items:
            items_str = ', '.join(loved_items[:5])
            parts.append(f"Absolutely love these items: {items_str}")
        if liked_items:
            items_str = ', '.join(liked_items[:5])
            parts.append(f"Like these items: {items_str}")
        if disliked_items:
            items_str = ', '.join(disliked_items[:5])
            parts.append(f"Dislike these items: {items_str}")
        if hated_items:
            items_str = ', '.join(hated_items[:5])
            parts.append(f"Never want these items: {items_str}")

        if parts:
            return ". ".join(parts)
        return ""


class MealPlan(models.Model):
    """
    Represents a generated meal plan for a user.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_plans')
    daily_menu = models.ForeignKey(DailyMenu, on_delete=models.CASCADE, related_name='meal_plans')
    
    # The recommended dishes with quantities
    dishes = models.ManyToManyField(Dish, through='MealPlanDish')
    
    # AI-generated explanation
    explanation = models.TextField(blank=True, help_text="AI-generated explanation of the meal plan")
    
    # Status
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved by User'),
        ('modified', 'Modified by User'),
        ('rejected', 'Rejected by User'),
        ('completed', 'Meal Completed'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True, help_text="When the plan was sent to user")
    approved_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        unique_together = ['user', 'daily_menu']
    
    def __str__(self):
        return f"Meal plan for {self.user.username} - {self.daily_menu}"
    
    def approve(self):
        """Mark the meal plan as approved"""
        self.status = 'approved'
        self.approved_at = timezone.now()
        self.save()
    
    def complete(self):
        """Mark the meal plan as completed"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()


class MealPlanDish(models.Model):
    """
    Through model for MealPlan-Dish relationship to store quantities.
    """
    meal_plan = models.ForeignKey(MealPlan, on_delete=models.CASCADE)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    quantity = models.FloatField(default=1.0, help_text="Number of servings")
    
    class Meta:
        unique_together = ['meal_plan', 'dish']
    
    def __str__(self):
        return f"{self.quantity}x {self.dish.name}"


class MealHistory(models.Model):
    """
    Records of meals actually eaten by users.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='meal_history')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='user_meals')
    daily_menu = models.ForeignKey(
        DailyMenu,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_history'
    )
    meal_plan = models.ForeignKey(
        MealPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='meal_history'
    )
    
    # Meal details
    quantity = models.FloatField(default=1.0, help_text="Number of servings")
    eaten_at = models.DateTimeField(default=timezone.now, db_index=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-eaten_at']
        verbose_name_plural = "Meal Histories"
    
    def __str__(self):
        return f"{self.user.username} ate {self.quantity}x {self.dish.name}"


class UserFeedback(models.Model):
    """
    User feedback on dishes with time-weighted ratings.
    
    Rating system:
    -2: Never want to eat this again
    -1: Bad but edible, may try again
     0: Neutral/indifferent
     1: Good, liked it
     2: Absolutely like it, include more
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='feedback')
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, related_name='feedback')
    meal_history = models.ForeignKey(
        MealHistory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='feedback'
    )
    
    # Feedback details
    RATING_CHOICES = [
        (-2, 'Never again'),
        (-1, 'Bad but edible'),
        (0, 'Neutral'),
        (1, 'Good'),
        (2, 'Love it'),
    ]
    rating = models.IntegerField(choices=RATING_CHOICES, db_index=True)
    comment = models.TextField(blank=True, help_text="Free-form feedback from user")
    
    # Metadata
    feedback_date = models.DateTimeField(default=timezone.now, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-feedback_date']
        verbose_name_plural = "User Feedback"
    
    def __str__(self):
        return f"{self.user.username}: {self.get_rating_display()} for {self.dish.name}"
    
    def get_weighted_rating(self, current_date=None):
        """
        Calculate time-weighted rating.
        Different decay rates based on rating value:
        - Negative ratings decay slower (longer memory of dislikes)
        - Positive ratings decay faster (preferences can change)
        - Neutral ratings decay fastest
        """
        if current_date is None:
            current_date = timezone.now()
        
        days_ago = (current_date - self.feedback_date).days
        
        # Different decay rates (half-life in days)
        if self.rating == -2:  # Never again
            half_life = 180  # 6 months
        elif self.rating == -1:  # Bad
            half_life = 90   # 3 months
        elif self.rating == 0:   # Neutral
            half_life = 30   # 1 month
        elif self.rating == 1:   # Good
            half_life = 60   # 2 months
        else:  # self.rating == 2, Love it
            half_life = 90   # 3 months
        
        # Exponential decay: weight = rating * (0.5 ^ (days / half_life))
        decay_factor = 0.5 ** (days_ago / half_life)
        return self.rating * decay_factor