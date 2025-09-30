import os
import json
import re
from datetime import date
from typing import Dict, List, Tuple, Optional

from openai import OpenAI

from .webpage import harvard_dining_menu_url
from .parser import (
    harvard_detailed_menu_retrieve,
    compute_meal_nutrition,
)


def _get_openai_client() -> OpenAI:
    """
    Create an OpenAI client using the OPENAI_API_KEY from environment variables.
    """
    import os
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY environment variable is not set.")
    return OpenAI(api_key=api_key)


def _get_default_model_name() -> str:
    """
    Resolve the model name from env or use a sensible lightweight default.
    """
    import os
    # Use environment variable or default to gpt-5
    return os.getenv("OPENAI_MODEL", "gpt-5")


def _safe_json_extract(text: str) -> Optional[dict]:
    """
    Try to extract a JSON object from arbitrary text.
    """
    if not text:
        return None
    # Fast path: direct JSON
    try:
        return json.loads(text)
    except Exception:
        pass
    # Fallback: find first {...} block
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def _parse_quantity_to_float(quantity: str) -> float:
    """
    Parse a quantity by extracting the first digit/number from the string. Defaults to 1.0.
    Handles cases like "1", "2.5", "1 serving", "2 portions", etc.
    """
    if quantity is None:
        return 1.0
    if isinstance(quantity, (int, float)):
        try:
            return float(quantity)
        except Exception:
            return 1.0
    
    text = str(quantity).strip()
    # Extract the first number (including decimals) from the string
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return 1.0
    try:
        return float(match.group(0))
    except Exception:
        return 1.0


def _call_openai_structured(prompt: str, schema_name: str, schema: Dict, temperature: float = 0.4) -> Optional[dict]:
    """
    Call OpenAI to produce JSON. Uses Chat Completions without response_format for compatibility.
    Note: temperature parameter is ignored for GPT-5 (only supports default of 1).
    """
    client = _get_openai_client()
    model = _get_default_model_name()
    
    # Call API without response_format and temperature (GPT-5 only supports default temperature of 1)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a careful assistant that outputs only valid JSON."},
            {"role": "user", "content": f"{prompt}\nReturn ONLY a valid JSON object."},
        ],
    )
    text = (response.choices[0].message.content or "") if getattr(response, "choices", None) else ""

    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        return _safe_json_extract(text)


def _call_openai_text(prompt: str, temperature: float = 0.6) -> str:
    """
    Call OpenAI for plain text using Chat Completions for compatibility.
    Note: temperature parameter is ignored for GPT-5 (only supports default of 1).
    """
    client = _get_openai_client()
    model = _get_default_model_name()
    # Call API without temperature (GPT-5 only supports default temperature of 1)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ],
    )
    if getattr(response, "choices", None):
        return response.choices[0].message.content or ""
    return ""


def _build_generation_prompt(simplified_menu: Dict, meal_type: str, user_prefs: str, nutritional_goals: Dict = None) -> str:
    """
    Build the prompt for generating a meal plan in strict JSON.

    Args:
        simplified_menu: Menu data with dish names and categories
        meal_type: Type of meal (breakfast, lunch, dinner)
        user_prefs: User preferences and feedback summary
        nutritional_goals: User's nutritional targets (optional)
    """
    meal_header = meal_type.capitalize()

    # Build nutritional context
    nutrition_context = ""
    if nutritional_goals:
        # Calculate approximate targets for this meal (divide daily goals by 3)
        meal_calories = nutritional_goals.get('target_calories', 2000) / 3
        meal_protein = nutritional_goals.get('target_protein', 50) / 3
        meal_carbs = nutritional_goals.get('target_carbs', 250) / 3
        meal_fat = nutritional_goals.get('target_fat', 70) / 3

        nutrition_context = (
            f"Nutritional targets for this {meal_type} (approximate 1/3 of daily goals):\n"
            f"- Calories: ~{int(meal_calories)} kcal\n"
            f"- Protein: ~{int(meal_protein)}g\n"
            f"- Carbohydrates: ~{int(meal_carbs)}g\n"
            f"- Fat: ~{int(meal_fat)}g\n"
            f"Consider fiber, sodium, and added sugars limits as well.\n"
        )

    # Reordered for caching: static content first, menu (semi-static), then user-specific data at end
    return (
        f"You are a helpful nutrition-focused meal planner.\n"
        f"Task: Propose a balanced {meal_header} from the provided HUDS menu by selecting 3-5 appropriate items.\n"
        f"CRITICAL: You MUST select items that EXACTLY match the names in the available menu below. "
        f"Do NOT create combinations, modify names, or invent new items. "
        f"Each item name must be copied exactly as shown in the menu.\n"
        f"Constraints: Respect user preferences and dietary restrictions. Use ONLY items present in the menu.\n"
        f"For quantity, specify the number of servings (e.g., '1', '2', '0.5', '1.5'). Use fractions for half servings.\n"
        f"Balance: Create nutritionally balanced meals that meet approximate targets while respecting preferences.\n"
        f"Output format: Return a JSON object with this exact structure:\n"
        f'{{\n'
        f'  "meals": [\n'
        f'    {{"name": "Item Name", "quantity": "1"}},\n'
        f'    {{"name": "Another Item", "quantity": "2"}}\n'
        f'  ]\n'
        f'}}\n'
        f"Available menu items (select ONLY from these exact names):\n{json.dumps(simplified_menu, ensure_ascii=False, indent=2)}\n\n"
        f"{nutrition_context}\n"
        f"User preferences and feedback: {user_prefs}\n"
    )


def _build_evaluation_prompt(meal_plan: Dict, nutrition_report: Dict, meal_type: str, user_prefs: str, nutritional_goals: Dict = None) -> str:
    """
    Build the prompt that asks the model to approve or reject the plan.

    Args:
        meal_plan: The proposed meal plan
        nutrition_report: Nutritional analysis of the plan
        meal_type: Type of meal (breakfast, lunch, dinner)
        user_prefs: User preferences and feedback
        nutritional_goals: User's nutritional targets (optional)
    """
    meal_header = meal_type.capitalize()

    # Build nutritional targets context
    nutrition_targets = ""
    if nutritional_goals:
        # Calculate approximate targets for this meal
        meal_calories = nutritional_goals.get('target_calories', 2000) / 3
        meal_protein = nutritional_goals.get('target_protein', 50) / 3
        meal_carbs = nutritional_goals.get('target_carbs', 250) / 3
        meal_fat = nutritional_goals.get('target_fat', 70) / 3
        max_sodium = nutritional_goals.get('max_sodium', 2300) / 3
        max_sugars = nutritional_goals.get('max_added_sugars', 50) / 3

        nutrition_targets = (
            f"Nutritional targets for this {meal_type} (approximate 1/3 of daily goals):\n"
            f"- Calories: ~{int(meal_calories)} kcal (current: {nutrition_report.get('totals', {}).get('calories', 0)})\n"
            f"- Protein: ~{int(meal_protein)}g (current: {nutrition_report.get('totals', {}).get('nutrition', {}).get('Protein', {}).get('amount', '0').rstrip('g')})\n"
            f"- Carbohydrates: ~{int(meal_carbs)}g\n"
            f"- Fat: ~{int(meal_fat)}g\n"
            f"- Max Sodium: ~{int(max_sodium)}mg\n"
            f"- Max Added Sugars: ~{int(max_sugars)}g\n"
        )

    return (
        f"You are a nutrition evaluator.\n"
        f"Assess whether the following {meal_header} plan is nutritionally balanced and meets targets while being consistent with user preferences.\n"
        f"Evaluate: adequate protein, fiber, controlled sodium/sugars, macronutrient balance, and preference alignment.\n"
        f"Approval criteria: Meets ~80% of nutritional targets AND aligns with user preferences.\n"
        f"Return JSON with this exact structure:\n"
        f'{{\n'
        f'  "approved": true/false,\n'
        f'  "reason": "Your assessment explanation"\n'
        f'}}\n'
        f"{nutrition_targets}\n"
        f"User preferences and feedback: {user_prefs}\n"
        f"MEAL_PLAN_JSON:\n{json.dumps(meal_plan, ensure_ascii=False)}\n"
        f"NUTRITION_SUMMARY_JSON:\n{json.dumps(nutrition_report, ensure_ascii=False)}\n"
    )


def _build_revision_prompt(previous_plan: Dict, critique: str, simplified_menu: Dict, meal_type: str, user_prefs: str, nutritional_goals: Dict = None) -> str:
    """
    Build the prompt to revise the plan based on critique.

    Args:
        previous_plan: The previous meal plan that was rejected
        critique: The reason for rejection/critique
        simplified_menu: Menu data with dish names and categories
        meal_type: Type of meal (breakfast, lunch, dinner)
        user_prefs: User preferences and feedback
        nutritional_goals: User's nutritional targets (optional)
    """
    meal_header = meal_type.capitalize()

    # Build nutritional context for revision
    nutrition_context = ""
    if nutritional_goals:
        # Calculate approximate targets for this meal
        meal_calories = nutritional_goals.get('target_calories', 2000) / 3
        meal_protein = nutritional_goals.get('target_protein', 50) / 3
        meal_carbs = nutritional_goals.get('target_carbs', 250) / 3
        meal_fat = nutritional_goals.get('target_fat', 70) / 3

        nutrition_context = (
            f"Nutritional targets for this {meal_type} (approximate 1/3 of daily goals):\n"
            f"- Calories: ~{int(meal_calories)} kcal\n"
            f"- Protein: ~{int(meal_protein)}g\n"
            f"- Carbohydrates: ~{int(meal_carbs)}g\n"
            f"- Fat: ~{int(meal_fat)}g\n"
            f"Consider fiber, sodium, and added sugars limits as well.\n"
        )

    return (
        f"Revise the {meal_header} plan to address the critique below while respecting user preferences and nutritional targets.\n"
        f"CRITICAL: You MUST select items that EXACTLY match the names in the available menu below. "
        f"Do NOT create combinations, modify names, or invent new items. "
        f"Each item name must be copied exactly as shown in the menu.\n"
        f"For quantity, specify the number of servings (e.g., '1', '2', '0.5', '1.5'). Use fractions for half servings.\n"
        f"Return JSON ONLY with this exact structure:\n"
        f'{{\n'
        f'  "meals": [\n'
        f'    {{"name": "Item Name", "quantity": "1"}},\n'
        f'    {{"name": "Another Item", "quantity": "2"}}\n'
        f'  ]\n'
        f'}}\n'
        f"{nutrition_context}"
        f"CRITIQUE TO ADDRESS:\n{critique}\n"
        f"PREVIOUS_PLAN_JSON:\n{json.dumps(previous_plan, ensure_ascii=False)}\n"
        f"User preferences and feedback: {user_prefs}\n"
        f"Available menu items (select ONLY from these exact names):\n{json.dumps(simplified_menu, ensure_ascii=False, indent=2)}\n"
    )


def _build_validation_error_prompt(invalid_items: List[str], simplified_menu: Dict, meal_type: str, user_prefs: str) -> str:
    """
    Build a prompt to correct invalid items in the meal plan.
    """
    meal_header = meal_type.capitalize()
    invalid_items_text = ", ".join(f'"{item}"' for item in invalid_items)
    return (
        f"ERROR: The following items in your {meal_header} plan are NOT available in the menu: {invalid_items_text}\n"
        f"You MUST select items that EXACTLY match the names in the available menu below.\n"
        f"Do NOT create combinations, modify names, or invent new items.\n"
        f"Each item name must be copied exactly as shown in the menu.\n"
        f"Return JSON ONLY with this exact structure:\n"
        f'{{\n'
        f'  "meals": [\n'
        f'    {{"name": "Item Name", "quantity": "1"}},\n'
        f'    {{"name": "Another Item", "quantity": "2"}}\n'
        f'  ]\n'
        f'}}\n'
        f"User preferences: {user_prefs}\n"
        f"Available menu items (select ONLY from these exact names):\n{json.dumps(simplified_menu, ensure_ascii=False, indent=2)}\n"
    )


def _build_final_message_prompt(meal_plan: Dict, nutrition_report: Dict, meal_type: str, user_prefs: str) -> str:
    """
    Build the final user-facing explanation prompt (free-form text, no JSON).
    """
    meal_header = meal_type.capitalize()

    # Extract meal items with quantities (no portion size suggestions)
    meal_items = []
    if meal_plan and meal_plan.get("meals"):
        for item in meal_plan["meals"]:
            name = item.get("name", "")
            quantity = item.get("quantity", "1")
            # Simple quantity formatting
            if quantity == "1" or quantity == 1:
                meal_items.append(f"• {name} (1 portion)")
            else:
                meal_items.append(f"• {name} ({quantity} portions)")

    meal_items_text = "\n".join(meal_items) if meal_items else "• Items to be determined based on your selection"

    return (
        f"Provide practical tips for the recommended {meal_header}. Focus on actionable suggestions, NOT justifications.\n"
        f"IMPORTANT: Note that 1 scoop = 1 portion. Do NOT suggest portion amounts or scoop counts.\n"
        f"Include:\n"
        f"• Drink suggestions (coffee, tea, water, juice pairings)\n"
        f"• Toppings to add (honey, nuts, berries, etc.)\n"
        f"• Sides or extras available at the dining hall\n"
        f"• Quick prep ideas if applicable\n"
        f"Keep it concise: 3-5 practical bullet points. No nutritional justifications. Do NOT mention portion sizes or scoop counts.\n"
        f"Do NOT include any JSON in the output. Be specific and actionable.\n"
        f"User preferences: {user_prefs}\n"
        f"Meal items with quantities:\n{meal_items_text}\n"
        f"Nutrition info: {nutrition_report.get('totals', {}).get('calories', 'N/A')} calories total\n"
        f"Note: 1 scoop = 1 portion for all items.\n"
        f"MEAL_PLAN_JSON:\n{json.dumps(meal_plan, ensure_ascii=False)}\n"
    )


def _meal_plan_to_quantity_mapping(meal_plan: Dict) -> Dict[str, float]:
    """
    Convert meal plan JSON into item -> quantity mapping for aggregation.
    """
    mapping: Dict[str, float] = {}
    if not meal_plan or not isinstance(meal_plan, dict):
        return mapping
    meals = meal_plan.get("meals") or []
    for entry in meals:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            continue
        qty = _parse_quantity_to_float(entry.get("quantity"))
        mapping[name] = qty
    return mapping


def _validate_meal_plan_items(meal_plan: Dict, simplified_menu: Dict) -> Tuple[List[str], List[str]]:
    """
    Validate that all items in the meal plan exist in the available menu.
    
    Parameters:
        meal_plan (Dict): The meal plan with items to validate
        simplified_menu (Dict): The available menu items
        
    Returns:
        Tuple[List[str], List[str]]: (valid_items, invalid_items)
    """
    if not meal_plan or not isinstance(meal_plan, dict):
        return [], []
    
    # Build a set of all available item names (case-insensitive)
    available_items = set()
    for category_items in simplified_menu.values():
        for item in category_items:
            if isinstance(item, dict) and 'name' in item:
                available_items.add(item['name'].strip().lower())
    
    valid_items = []
    invalid_items = []
    
    meals = meal_plan.get("meals") or []
    for entry in meals:
        if not isinstance(entry, dict):
            continue
        name = (entry.get("name") or "").strip()
        if not name:
            continue
            
        # Check if the item exists in the menu (case-insensitive)
        if name.lower() in available_items:
            valid_items.append(name)
        else:
            invalid_items.append(name)
    
    return valid_items, invalid_items


def _clear_openai_context() -> None:
    """
    Clear the context before starting a new dialog by making a simple API call.
    This helps ensure the model doesn't carry over context from previous conversations.
    """
    try:
        client = _get_openai_client()
        model = _get_default_model_name()
        # Make a simple call to reset context
        client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Context cleared."},
                {"role": "user", "content": "Context cleared. Ready for new task."},
            ],
        )
    except Exception as e:
        # Don't fail the main process if context clearing fails
        print(f"⚠️  Warning: Could not clear OpenAI context: {e}")


def create_meal(dt: date, meal_type: str, user_prefs: str, menu_data: Dict = None, nutritional_goals: Dict = None) -> Dict:
    """
    Create a nutritionally balanced meal recommendation for the given HUDS menu.

    Parameters:
        dt (date): Date of the menu.
        meal_type (str): One of "breakfast", "lunch", or "dinner" (case-insensitive).
        user_prefs (str): Free-form user preferences/restrictions and feedback summary.
        menu_data (Dict, optional): Pre-fetched menu data from database. If None, fetches from web.
        nutritional_goals (Dict, optional): User's nutritional targets (calories, protein, carbs, fat, etc.)

    Returns:
        Dict: {
            'explanation': str,  # User-friendly explanation
            'meals': List[Dict],  # List of {'name': str, 'quantity': str/float}
            'nutrition': Dict  # Nutrition report
        }
    """
    print(f"🍽️  Starting meal creation for {meal_type} on {dt}")
    print(f"👤 User preferences: {user_prefs}")
    
    if not isinstance(dt, date):
        raise ValueError("dt must be a datetime.date instance")

    meal_norm = (meal_type or "").strip().lower()
    if meal_norm not in {"breakfast", "lunch", "dinner"}:
        raise ValueError("meal_type must be one of: breakfast, lunch, dinner")

    # Use provided menu data or fetch from web
    if menu_data is not None:
        print("📊 Using pre-loaded menu data from database")
        detailed_menu = menu_data
    else:
        print("🌐 Fetching menu data from web...")
        url = harvard_dining_menu_url(dt, meal_norm.capitalize())
        detailed_menu = harvard_detailed_menu_retrieve(url)
        if not isinstance(detailed_menu, dict) or "menu" not in detailed_menu:
            raise RuntimeError("Failed to retrieve HUDS menu for the specified date/meal")
    
    print("✅ Menu data loaded successfully!")
    print(f"📊 Found {len(detailed_menu.get('menu', {}))} menu categories")
    
    # Create a simplified menu structure for the AI (just name, category, portion)
    simplified_menu = {}
    for category_name, items in detailed_menu.get('menu', {}).items():
        simplified_menu[category_name] = []
        for item in items:
            simplified_item = {
                "name": item.get("name", ""),
                "portion": item.get("portion", ""),
                "category": category_name
            }
            simplified_menu[category_name].append(simplified_item)
    
    print(f"📝 Simplified menu structure created with {sum(len(items) for items in simplified_menu.values())} total items")
    print(f"📊 Simplified menu size: {len(json.dumps(simplified_menu, ensure_ascii=False))} characters")
    print("🤖 Starting AI-powered meal planning process...")
    
    # Clear OpenAI context before starting
    print("🧹 Clearing OpenAI context...")
    _clear_openai_context()

    # Iterative generate/evaluate loop (max 5 attempts)
    attempts = 0
    best_plan: Optional[Dict] = None
    best_plan_reason: str = ""

    # JSON Schemas for generation and evaluation
    generation_schema: Dict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "meals": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "name": {"type": "string", "minLength": 1},
                        "quantity": {"type": "string", "minLength": 1},
                    },
                    "required": ["name", "quantity"],
                },
            }
        },
        "required": ["meals"],
    }

    evaluation_schema: Dict = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "approved": {"type": "boolean"},
            "reason": {"type": "string"},
        },
        "required": ["approved", "reason"],
    }

    while attempts < 5:
        attempts += 1
        print(f"\n🔄 Attempt {attempts}/5: Generating meal plan...")
        
        if best_plan is None:
            gen_prompt = _build_generation_prompt(simplified_menu, meal_norm, user_prefs, nutritional_goals)
            print("📝 Building initial meal plan prompt...")
        else:
            # Use last critique to revise
            gen_prompt = _build_revision_prompt(best_plan, best_plan_reason, simplified_menu, meal_norm, user_prefs, nutritional_goals)
            print("📝 Building revision prompt based on feedback...")

        print("🤖 Calling OpenAI to generate meal plan...")
        print(f"📤 PROMPT LENGTH: {len(gen_prompt)} characters")
        print(f"📤 PROMPT PREVIEW: {gen_prompt[:200]}...")
        
        plan_json = _call_openai_structured(
            gen_prompt,
            schema_name="MealPlan",
            schema=generation_schema,
            temperature=0.5,
        )
        
        print(f"📥 MODEL RESPONSE: {plan_json}")
        
        if not plan_json or not isinstance(plan_json, dict) or not plan_json.get("meals"):
            print("❌ Model failed to produce valid meal plan, trying again...")
            continue
        
        print(f"✅ Generated meal plan: {[item.get('name', 'Unknown') for item in plan_json.get('meals', [])]}")
        
        # Validate that all items exist in the menu
        print("🔍 Validating meal plan items...")
        valid_items, invalid_items = _validate_meal_plan_items(plan_json, simplified_menu)
        
        if invalid_items:
            print(f"❌ Invalid items found: {invalid_items}")
            print("🔄 Requesting correction from model...")
            
            # Use validation error prompt to get corrected plan
            validation_prompt = _build_validation_error_prompt(invalid_items, simplified_menu, meal_norm, user_prefs)
            print(f"📤 VALIDATION PROMPT LENGTH: {len(validation_prompt)} characters")
            
            corrected_plan = _call_openai_structured(
                validation_prompt,
                schema_name="MealPlan",
                schema=generation_schema,
                temperature=0.3,  # Lower temperature for more precise corrections
            )
            
            if corrected_plan and isinstance(corrected_plan, dict) and corrected_plan.get("meals"):
                print(f"📥 CORRECTED PLAN: {corrected_plan}")
                # Validate the corrected plan
                valid_items_corrected, invalid_items_corrected = _validate_meal_plan_items(corrected_plan, simplified_menu)
                if not invalid_items_corrected:
                    print("✅ Correction successful, using corrected plan")
                    plan_json = corrected_plan
                else:
                    print(f"❌ Correction failed, still has invalid items: {invalid_items_corrected}")
                    print("🔄 Continuing with original plan for nutrition calculation...")
            else:
                print("❌ Model failed to provide corrected plan, continuing with original...")
        else:
            print("✅ All items are valid!")
        
        print("🧮 Computing nutrition for selected items...")
        quantities = _meal_plan_to_quantity_mapping(plan_json)
        nutrition_report = compute_meal_nutrition(detailed_menu, quantities)

        print("🤖 Calling OpenAI to evaluate meal plan...")
        eval_prompt = _build_evaluation_prompt(plan_json, nutrition_report, meal_norm, user_prefs, nutritional_goals)
        print(f"📤 EVAL PROMPT LENGTH: {len(eval_prompt)} characters")
        print(f"📤 EVAL PROMPT PREVIEW: {eval_prompt[:200]}...")
        
        eval_json = _call_openai_structured(
            eval_prompt,
            schema_name="MealEvaluation",
            schema=evaluation_schema,
            temperature=0.2,
        )
        
        print(f"📥 EVAL RESPONSE: {eval_json}")
        
        # Handle both "approve" and "approved" field names
        approve = False
        if isinstance(eval_json, dict):
            approve = bool(eval_json.get("approve") or eval_json.get("approved"))
        reason = (eval_json.get("reason") if isinstance(eval_json, dict) else None) or ""
        
        print(f"📊 Evaluation result: {'✅ APPROVED' if approve else '❌ NEEDS REVISION'}")
        if reason:
            print(f"💭 Feedback: {reason}")

        best_plan = plan_json
        best_plan_reason = reason

        if approve or attempts >= 5:
            print("🎯 Finalizing meal recommendation...")
            # Final explanation for the user
            final_prompt = _build_final_message_prompt(best_plan, nutrition_report, meal_norm, user_prefs)
            print(f"📤 FINAL PROMPT LENGTH: {len(final_prompt)} characters")
            print(f"📤 FINAL PROMPT PREVIEW: {final_prompt[:200]}...")
            print("🤖 Generating final user-friendly explanation...")
            
            final_response = _call_openai_text(final_prompt, temperature=0.6)
            print(f"📥 FINAL RESPONSE: {final_response}")
            
            # Return structured data with explanation, meals, and nutrition
            return {
                'explanation': final_response,
                'meals': best_plan.get('meals', []),
                'nutrition': nutrition_report
            }

    # Fallback if loop exits unexpectedly
    return {
        'explanation': "Sorry, I couldn't generate a satisfactory meal plan at this time. Please try again.",
        'meals': [],
        'nutrition': {}
    }

