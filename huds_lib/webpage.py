from datetime import date

def harvard_dining_menu_url(dt: date, meal: str) -> str:
    """
    Generate a Harvard Dining Services menu URL for a given date and meal.

    Parameters:
        dt (date): The date (datetime.date object).
        meal (str): One of "Breakfast", "Lunch", "Dinner".

    Returns:
        str: The full URL.
    """
    base_url = "https://www.foodpro.huds.harvard.edu/foodpro/longmenucopy.aspx"
    
    # Format date as M%2fD%2fYYYY
    dt_str = f"{dt.month}%2f{dt.day}%2f{dt.year}"
    
    # Normalize meal input
    meal = meal.capitalize()
    if meal not in ["Breakfast", "Lunch", "Dinner"]:
        raise ValueError("Meal must be 'Breakfast', 'Lunch', or 'Dinner'")
    
    meal_param = f"{meal}+Menu"
    
    return (
        f"{base_url}?"
        "sName=HARVARD+UNIVERSITY+DINING+SERVICES"
        "&locationNum=30"
        "&locationName=Dining+Hall"
        "&naFlag=1"
        "&WeeksMenus=This+Week%27s+Menus"
        f"&dtdate={dt_str}"
        f"&mealName={meal_param}"
    )

