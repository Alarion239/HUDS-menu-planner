import time
import requests
from bs4 import BeautifulSoup
import json
import re
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse, parse_qs, urljoin

# Reusable HTTP session with browser-like headers (helps avoid 403/blocks)
_HTTP_SESSION = None


def _get_http_session() -> requests.Session:
    global _HTTP_SESSION
    if _HTTP_SESSION is None:
        session = requests.Session()
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        _HTTP_SESSION = session
    return _HTTP_SESSION


# =============================================================================
# BASIC MENU PARSER FUNCTIONS (from menu_parser.py)
# =============================================================================

def harvard_dining_menu_retrieve(url: str) -> Dict:
    """
    Retrieve and parse a Harvard Dining Services menu page into structured JSON.
    
    Parameters:
        url (str): The Harvard Dining menu URL to parse
        
    Returns:
        Dict: Structured JSON containing menu categories and items with metadata
    """
    try:
        # Fetch the HTML content
        session = _get_http_session()
        # Provide a reasonable referer for the main menu page
        referer = 'https://www.foodpro.huds.harvard.edu/foodpro/'
        response = session.get(url, timeout=15, allow_redirects=True, headers={'Referer': referer})
        response.raise_for_status()
        html_content = response.text
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract menu metadata
        menu_metadata = _extract_menu_metadata(soup, url)
        
        # Extract menu categories and items
        menu_data = _extract_menu_data(soup)
        
        # Combine metadata and menu data
        result = {
            "metadata": menu_metadata,
            "menu": menu_data
        }
        
        return result
        
    except requests.RequestException as e:
        return {"error": f"Failed to fetch URL: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to parse menu: {str(e)}"}


def _extract_menu_metadata(soup: BeautifulSoup, url: str) -> Dict:
    """Extract metadata about the menu (date, meal, location, etc.)"""
    metadata = {}
    
    # Extract from URL parameters
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    
    if 'dtdate' in query_params:
        date_str = query_params['dtdate'][0].replace('%2f', '/')
        metadata['date'] = date_str
    
    if 'mealName' in query_params:
        meal_name = query_params['mealName'][0].replace('+', ' ')
        metadata['meal'] = meal_name
    
    if 'locationName' in query_params:
        metadata['location'] = query_params['locationName'][0].replace('+', ' ')
    
    # Extract menu title from HTML
    title_element = soup.find('div', class_='longmenugridheader')
    if title_element:
        title_text = title_element.get_text(strip=True)
        metadata['title'] = title_text
        
        # Try to extract date from title if not in URL
        if 'date' not in metadata:
            date_match = re.search(r'(\w+day, \w+ \d+, \d{4})', title_text)
            if date_match:
                metadata['date'] = date_match.group(1)
    
    return metadata


def _extract_menu_data(soup: BeautifulSoup) -> Dict:
    """Extract menu categories and items from the HTML"""
    menu_data = {}
    
    # Find the main table containing menu items
    main_table = None
    for table in soup.find_all('table'):
        if table.find('div', class_='longmenucolmenucat'):
            main_table = table
            break
    
    if not main_table:
        return menu_data
    
    # Process table rows sequentially
    rows = main_table.find_all('tr')
    current_category = None
    seen_items = set()  # To avoid duplicates
    
    for row in rows:
        # Check for category
        category_elem = row.find('div', class_='longmenucolmenucat')
        if category_elem:
            current_category = _clean_category_name(category_elem.get_text(strip=True))
            if current_category not in menu_data:
                menu_data[current_category] = []
            continue
        
        # Check for menu item
        item_elem = row.find('div', class_='longmenucoldispname')
        if item_elem and current_category:
            item_data = _extract_item_data(item_elem, row)
            if item_data:
                # Create a unique key for deduplication (just use name)
                item_key = item_data['name']
                
                # If we haven't seen this item, add it
                if item_key not in seen_items:
                    seen_items.add(item_key)
                    menu_data[current_category].append(item_data)
                else:
                    # If we have seen it, replace if this one has better portion info
                    existing_items = menu_data[current_category]
                    for i, existing_item in enumerate(existing_items):
                        if existing_item['name'] == item_key:
                            # Prefer items with portion information
                            if not existing_item['portion'] and item_data['portion']:
                                existing_items[i] = item_data
                            break
    
    return menu_data


def _clean_category_name(category_text: str) -> str:
    """Clean category name by removing dashes and extra spaces"""
    # Remove leading/trailing dashes and spaces
    cleaned = re.sub(r'^[- ]+|-+$', '', category_text).strip()
    return cleaned


def _extract_item_data(item_element: BeautifulSoup, row: BeautifulSoup) -> Optional[Dict]:
    """Extract data for a single menu item"""
    try:
        # Extract item name from the link
        link_element = item_element.find('a')
        if not link_element:
            return None
            
        item_name = link_element.get_text(strip=True)
        
        # Extract portion size
        portion_element = row.find('div', class_='longmenucolportions')
        portion_size = ""
        if portion_element:
            portion_text = portion_element.get_text(strip=True)
            # Clean up portion text (remove &nbsp; entities)
            portion_size = re.sub(r'&nbsp;', ' ', portion_text).strip()
        
        # Extract detail URL
        detail_url = ""
        if link_element.get('href'):
            detail_url = link_element.get('href')
            # Convert relative URLs to absolute using urljoin
            detail_url = urljoin('https://www.foodpro.huds.harvard.edu/foodpro/', detail_url)
        
        item_data = {
            "name": item_name,
            "portion": portion_size,
            "detail_url": detail_url
        }
        
        return item_data
        
    except Exception as e:
        print(f"Error extracting item data: {e}")
        return None


# =============================================================================
# NUTRITION PARSER FUNCTIONS (from nutrition_parser.py)
# =============================================================================

def harvard_nutrition_label_retrieve(url: str) -> Dict:
    """
    Retrieve and parse a Harvard Dining Services nutrition label page into structured JSON.
    
    Parameters:
        url (str): The Harvard Dining nutrition label URL to parse
        
    Returns:
        Dict: Structured JSON containing nutrition facts and ingredients
    """
    try:
        # Add 100ms delay for server health
        #time.sleep(0.1)
        
        # Normalize possibly-relative URL and fetch the HTML content
        session = _get_http_session()
        # Nutrition detail endpoints sometimes check Referer/UA
        referer = 'https://www.foodpro.huds.harvard.edu/foodpro/'
        if not re.match(r'^https?://', url, flags=re.IGNORECASE):
            url = urljoin('https://www.foodpro.huds.harvard.edu/foodpro/', url)
        response = session.get(url, timeout=20, allow_redirects=True, headers={'Referer': referer})
        response.raise_for_status()
        html_content = response.text
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract all nutrition data
        nutrition_data = _extract_nutrition_data(soup)
        
        return nutrition_data
        
    except requests.RequestException as e:
        return {"error": f"Failed to fetch URL: {str(e)}"}
    except Exception as e:
        return {"error": f"Failed to parse nutrition label: {str(e)}"}


def _extract_nutrition_data(soup: BeautifulSoup) -> Dict:
    """Extract all nutrition data from the HTML"""
    result = {}
    
    # Extract food name
    food_name_elem = soup.find('div', class_='labelrecipe')
    if food_name_elem:
        result['name'] = food_name_elem.get_text(strip=True)
    
    # Extract serving size
    serving_size_elems = soup.find_all('div', class_='nutfactsservsize')
    if len(serving_size_elems) > 1:  # The second one usually contains the actual serving size
        result['serving_size'] = serving_size_elems[1].get_text(strip=True)
    
    # Extract calories
    calories_elem = soup.find('td', class_='nutfactscaloriesval')
    if calories_elem:
        calories_text = calories_elem.get_text(strip=True)
        try:
            result['calories'] = int(calories_text)
        except ValueError:
            result['calories'] = calories_text
    
    # Extract ingredients
    ingredients_elem = soup.find('span', class_='labelingredientsvalue')
    if ingredients_elem:
        ingredients_text = ingredients_elem.get_text(strip=True)
        result['ingredients'] = _parse_ingredients(ingredients_text)
    
    # Extract nutrition facts
    result['nutrition'] = _extract_nutrition_facts(soup)
    
    return result


def _parse_ingredients(ingredients_text: str) -> List[str]:
    """Parse ingredients from the ingredients text"""
    if not ingredients_text:
        return []
    
    # Split by commas and clean up each ingredient
    ingredients = []
    current_ingredient = ""
    paren_depth = 0
    
    for char in ingredients_text:
        if char == '(':
            paren_depth += 1
        elif char == ')':
            paren_depth -= 1
        elif char == ',' and paren_depth == 0:
            if current_ingredient.strip():
                ingredients.append(current_ingredient.strip())
            current_ingredient = ""
            continue
        
        current_ingredient += char
    
    # Add the last ingredient
    if current_ingredient.strip():
        ingredients.append(current_ingredient.strip())
    
    return ingredients


def _extract_nutrition_facts(soup: BeautifulSoup) -> Dict:
    """Extract nutrition facts with amounts and daily values"""
    nutrition = {}
    
    # Find the main nutrition facts table
    main_table = soup.find('table', {'border': '1', 'align': 'center', 'width': '1200'})
    if main_table:
        # Extract from the structured nutrition facts rows
        nutrition.update(_extract_structured_nutrition(main_table))
    
    # Clean up nutrition facts and handle special cases
    nutrition = _clean_nutrition_facts(nutrition)
    
    return nutrition


def _extract_structured_nutrition(main_table: BeautifulSoup) -> Dict:
    """Extract nutrition facts from the structured nutrition table (main panel only)"""
    nutrition = {}
    
    # Find all table rows within the main table
    rows = main_table.find_all('tr', recursive=False)
    
    # We only want to process the first ~6-7 rows which contain the main nutrition panel
    # The rest is a summary table that has duplicate/inconsistent data
    # Look for rows that have either the left nutrition facts panel or the right side nutrients
    for row in rows[:10]:  # Limit to first 10 rows to avoid the summary table
        cells = row.find_all('td')
        
        # Look for rows with nutrition information
        for cell in cells:
            # Skip cells that contain <li> tags (those are from the summary table)
            if cell.find('li'):
                continue
                
            nutrition_spans = cell.find_all('span', class_='nutfactstopnutrient')
            
            # Process pairs of spans (amount and daily value)
            for i in range(0, len(nutrition_spans), 2):
                amount_span = nutrition_spans[i]
                dv_span = nutrition_spans[i + 1] if i + 1 < len(nutrition_spans) else None
                
                amount_text = amount_span.get_text(strip=True)
                dv_text = dv_span.get_text(strip=True) if dv_span else ""
                
                # Parse the nutrition information
                parsed = _parse_structured_nutrition_text(amount_text)
                if parsed:
                    name, amount = parsed
                    daily_value = dv_text if dv_text and re.match(r'^\d+%$', dv_text) else None
                    
                    # Add to nutrition dict if not already present or if this has better data
                    if name not in nutrition:
                        nutrition[name] = {
                            "amount": amount,
                            "daily_value": daily_value
                        }
    
    return nutrition


def _parse_structured_nutrition_text(text: str) -> Optional[tuple]:
    """Parse structured nutrition text to extract nutrient name and amount"""
    # Store original text before any cleanup
    original_text = text
    
    # Skip empty or placeholder texts
    if not text or text in ['&nbsp;', ' ', '<b>', '</b>']:
        return None
    
    # Skip standalone percentages
    if re.match(r'^\d+%$', text):
        return None
    
    # Create versions with different cleanup levels
    text_no_bold = re.sub(r'</?b>', '', text).replace('&nbsp;', ' ').strip()
    
    # Pattern to match various nutrition fact formats
    patterns = [
        # "Total Fat10g" (no space between name and amount - common when bold tags are removed)
        r'^(.+?)([\d.-]+(?:\.\d+)?[a-zA-Z]+)$',
        # "<b>Total Fat&nbsp;</b>10g" (with bold tags and nbsp)
        r'^<b>(.+?)(?:&nbsp;|\s)*</b>\s*([\d.-]+(?:\.\d+)?[a-zA-Z]+)$',
        # "<b>Total Fat </b>10g" (with bold tags)
        r'^<b>(.+?)\s*</b>\s*([\d.-]+(?:\.\d+)?[a-zA-Z]+)$',
        # "Total Fat 10g" (with space)
        r'^(.+?)\s+([\d.-]+(?:\.\d+)?[a-zA-Z]+)$',
        # "    Saturated Fat 3g" (with indentation)
        r'^\s*(.+?)\s+([\d.-]+(?:\.\d+)?[a-zA-Z]+)$'
    ]
    
    # Try patterns on both original and cleaned text
    texts_to_try = [original_text, text_no_bold]
    
    for text_variant in texts_to_try:
        for pattern in patterns:
            match = re.match(pattern, text_variant)
            if match:
                name = match.group(1).strip()
                amount = match.group(2).strip()
                
                # Clean up name
                name = re.sub(r'\s+', ' ', name)
                name = name.replace('Total Carbohydrate.', 'Total Carbohydrate')
                
                # Skip certain entries
                if name.lower().startswith('includes'):
                    continue
                    
                # Normalize some names
                if 'trans' in name.lower() and 'fat' in name.lower():
                    name = 'Trans Fat'
                elif 'fatty acid' in name.lower():
                    name = 'Trans Fat'
                elif name == 'Carbohydrates':
                    name = 'Total Carbohydrate'
                elif 'vitamin d' in name.lower():
                    name = 'Vitamin D'
                
                return (name, amount)
    
    return None


def _parse_nutrition_text(text: str) -> Optional[tuple]:
    """Parse nutrition text to extract name, amount, and daily value"""
    # Remove leading whitespace indicators
    text = re.sub(r'^[\s\u00a0]*', '', text)
    
    # Skip empty or just percentage values
    if not text or text == '&nbsp;' or re.match(r'^\d+%$', text):
        return None
    
    # Handle different formats:
    # "Total Fat 10g" -> name, amount, no daily value
    # "13%" -> just daily value (skip these standalone percentages)
    # "Saturated Fat 3g" -> name, amount, no daily value
    # "Calories 160kcal 8%" -> name, amount, daily value
    
    # Skip standalone percentages
    if re.match(r'^\d+%$', text):
        return None
    
    # Pattern for nutrition facts with amount and optionally daily value
    # Examples: "Total Fat 10g", "Saturated Fat 3g", "Calories 160kcal 8%"
    pattern = r'^(.+?)\s+([\d.-]+(?:\.\d+)?[a-zA-Z]+)(?:\s+(\d+%))?'
    match = re.match(pattern, text)
    
    if match:
        name = match.group(1).strip()
        amount = match.group(2).strip()
        daily_value = match.group(3) if match.group(3) else None
        
        # Clean up name
        name = re.sub(r'\s+', ' ', name)
        name = name.replace('&nbsp;', ' ').strip()
        
        # Handle special cases
        if 'Trans' in name and 'Fat' in name:
            name = 'Trans Fat'
        elif 'Vitamin D' in name:
            name = 'Vitamin D'
        elif 'Added Sugar' in name:
            name = 'Added Sugars'
        elif 'Total Carbohydrate.' in name:
            name = 'Total Carbohydrate'
        
        return (name, amount, daily_value)
    
    return None


def _clean_nutrition_facts(nutrition: Dict) -> Dict:
    """Clean up and organize nutrition facts"""
    cleaned = {}
    
    # Define the order we want for nutrition facts
    desired_order = [
        'Total Fat', 'Saturated Fat', 'Trans Fat',
        'Cholesterol', 'Sodium', 'Total Carbohydrate',
        'Dietary Fiber', 'Total Sugars', 'Added Sugars',
        'Protein', 'Vitamin D', 'Calcium', 'Iron', 'Potassium'
    ]
    
    # Add nutrition facts in desired order
    for key in desired_order:
        if key in nutrition:
            cleaned[key] = nutrition[key]
    
    # Add any remaining nutrition facts not in the standard list
    for key, value in nutrition.items():
        if key not in cleaned and key not in ['Calories', 'Fat', 'Carbohydrates']:  # Skip duplicates
            cleaned[key] = value
    
    return cleaned


# =============================================================================
# DETAILED MENU PARSER FUNCTIONS (from detailed_menu_parser.py)
# =============================================================================

def harvard_detailed_menu_retrieve(url: str, delay_between_requests: float = 0.0, max_retries: int = 3, quiet: bool = True) -> Dict:
    """
    Retrieve and parse a Harvard Dining Services menu page with complete nutritional details.
    
    This function combines the menu parser and nutrition parser to provide a comprehensive
    menu structure with full nutrition information for each item.
    
    Parameters:
        url (str): The Harvard Dining menu URL to parse
        delay_between_requests (float): Delay in seconds between nutrition requests (default: 0.5)
        max_retries (int): Maximum number of retries for failed nutrition requests (default: 3)
        
    Returns:
        Dict: Structured JSON containing menu categories with complete nutrition details
    """
    
    # First, get the basic menu structure
    if not quiet:
        print("Fetching menu structure...")
    menu_data = harvard_dining_menu_retrieve(url)
    
    if "error" in menu_data:
        return menu_data
    
    # Initialize the detailed menu structure
    detailed_menu = {
        "metadata": menu_data["metadata"],
        "menu": {},
        "nutrition_fetch_stats": {
            "total_items": 0,
            "successful_fetches": 0,
            "failed_fetches": 0,
            "items_without_urls": 0
        }
    }
    
    total_items = sum(len(items) for items in menu_data["menu"].values())
    current_item = 0
    
    if not quiet:
        print(f"Found {total_items} menu items. Fetching nutrition details...")
    
    # Process each category and item
    for category_name, items in menu_data["menu"].items():
        if not quiet:
            print(f"\nProcessing category: {category_name}")
        detailed_menu["menu"][category_name] = []
        
        for item in items:
            current_item += 1
            detailed_menu["nutrition_fetch_stats"]["total_items"] += 1
            
            if quiet:
                # Single-line loading bar update
                progress = f"[{current_item}/{total_items}]"
                print(f"\rFetching nutrition {progress}...", end="", flush=True)
            else:
                print(f"  [{current_item}/{total_items}] {item['name'][:50]}...")
            
            # Create the detailed item structure
            detailed_item = {
                "name": item["name"],
                "portion": item.get("portion", ""),
                "detail_url": item.get("detail_url", ""),
                "nutrition": None,
                "nutrition_fetch_status": "not_attempted"
            }
            
            # Try to fetch nutrition information if URL is available
            if item.get("detail_url"):
                nutrition_data = _fetch_nutrition_with_retry(
                    item["detail_url"], 
                    max_retries,
                    delay_between_requests
                )
                
                if nutrition_data and "error" not in nutrition_data:
                    detailed_item["nutrition"] = nutrition_data
                    detailed_item["nutrition_fetch_status"] = "success"
                    detailed_menu["nutrition_fetch_stats"]["successful_fetches"] += 1
                    if not quiet:
                        print(f"    ✓ Nutrition data fetched")
                else:
                    detailed_item["nutrition_fetch_status"] = "failed"
                    detailed_item["nutrition_error"] = nutrition_data.get("error", "Unknown error") if nutrition_data else "No response"
                    detailed_menu["nutrition_fetch_stats"]["failed_fetches"] += 1
                    if not quiet:
                        print(f"    ✗ Failed to fetch nutrition data")
            else:
                detailed_item["nutrition_fetch_status"] = "no_url"
                detailed_menu["nutrition_fetch_stats"]["items_without_urls"] += 1
                if not quiet:
                    print(f"    - No nutrition URL available")
            
            detailed_menu["menu"][category_name].append(detailed_item)
            
            # Add delay between requests to be respectful to the server
            if item.get("detail_url") and delay_between_requests > 0:
                time.sleep(delay_between_requests)
    
    # Print summary statistics
    stats = detailed_menu["nutrition_fetch_stats"]
    if quiet:
        # Finish the loading line
        print()
    print(f"\n" + "="*60)
    print("NUTRITION FETCH SUMMARY:")
    print(f"Total items: {stats['total_items']}")
    print(f"Successful fetches: {stats['successful_fetches']}")
    print(f"Failed fetches: {stats['failed_fetches']}")
    print(f"Items without URLs: {stats['items_without_urls']}")
    success_rate = (stats['successful_fetches']/stats['total_items']*100) if stats['total_items'] else 0.0
    print(f"Success rate: {success_rate:.1f}%")
    print("="*60)
    
    return detailed_menu


def _fetch_nutrition_with_retry(url: str, max_retries: int, delay: float) -> Optional[Dict]:
    """
    Fetch nutrition data with retry logic
    
    Parameters:
        url (str): The nutrition detail URL
        max_retries (int): Maximum number of retry attempts
        delay (float): Delay between retry attempts
        
    Returns:
        Optional[Dict]: Nutrition data or None if all retries failed
    """
    
    for attempt in range(max_retries):
        try:
            nutrition_data = harvard_nutrition_label_retrieve(url)
            
            # Check if we got valid data
            if nutrition_data and "error" not in nutrition_data:
                return nutrition_data
            elif attempt < max_retries - 1:  # Not the last attempt
                error_message = None
                if isinstance(nutrition_data, dict):
                    error_message = nutrition_data.get("error")
                if not error_message:
                    error_message = str(nutrition_data)
                print(f"    Error: {error_message}")
                print(f"    Retry {attempt + 1}/{max_retries} in {delay}s...")
                time.sleep(delay)
            else:
                return nutrition_data  # Return the error on last attempt
                
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    Error: {str(e)}")
                print(f"    Retry {attempt + 1}/{max_retries} in {delay}s...")
                time.sleep(delay)
            else:
                return {"error": f"Exception after {max_retries} attempts: {str(e)}"}
    
    return {"error": f"Failed after {max_retries} attempts"}


def harvard_detailed_menu_retrieve_lite(url: str, max_items_per_category: int = 5) -> Dict:
    """
    Retrieve a limited version of the detailed menu (useful for testing or quick previews).
    
    Parameters:
        url (str): The Harvard Dining menu URL to parse
        max_items_per_category (int): Maximum number of items to fetch per category (default: 5)
        
    Returns:
        Dict: Structured JSON containing limited menu with nutrition details
    """
    
    print(f"Fetching lite menu (max {max_items_per_category} items per category)...")
    
    # Get the basic menu structure
    menu_data = harvard_dining_menu_retrieve(url)
    
    if "error" in menu_data:
        return menu_data
    
    # Create a limited version of the menu
    limited_menu_data = {
        "metadata": menu_data["metadata"],
        "menu": {}
    }
    
    for category_name, items in menu_data["menu"].items():
        limited_menu_data["menu"][category_name] = items[:max_items_per_category]
    
    # Use the full detailed parser on the limited data
    temp_url = url  # We'll use the original URL but modify the logic
    detailed_data = harvard_detailed_menu_retrieve(temp_url, delay_between_requests=0.3)
    
    # Filter the results to match our limited items
    if "error" not in detailed_data:
        filtered_menu = {}
        for category_name, items in detailed_data["menu"].items():
            filtered_menu[category_name] = items[:max_items_per_category]
        
        detailed_data["menu"] = filtered_menu
        detailed_data["metadata"]["note"] = f"Limited to {max_items_per_category} items per category"
    
    return detailed_data


# Helper function to save results to JSON file
def save_detailed_menu_to_file(detailed_menu: Dict, filename: str) -> bool:
    """
    Save detailed menu data to a JSON file
    
    Parameters:
        detailed_menu (Dict): The detailed menu data
        filename (str): Output filename
        
    Returns:
        bool: True if successful, False otherwise
    """
    import json
    
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(detailed_menu, f, indent=2, ensure_ascii=False)
        print(f"Detailed menu saved to: {filename}")
        return True
    except Exception as e:
        print(f"Error saving to file: {str(e)}")
        return False


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def _format_json_output(data: Dict, indent: int = 2) -> str:
    """Format the parsed data as pretty JSON string"""
    return json.dumps(data, indent=indent, ensure_ascii=False)


# =============================================================================
# AGGREGATION FUNCTIONS
# =============================================================================

def _parse_amount_to_value_unit(amount_text: str) -> Optional[Tuple[float, str]]:
    """Parse a nutrient amount string like "10g", "70mg", "2mcg" into (value, unit)."""
    if not amount_text or not isinstance(amount_text, str):
        return None
    text = amount_text.strip().lower().replace(' ', '')
    match = re.match(r'^(-?\d+(?:\.\d+)?)([a-zA-Z]+)$', text)
    if not match:
        return None
    try:
        value = float(match.group(1))
        unit = match.group(2)
        return value, unit
    except ValueError:
        return None


def _convert_to_grams(value: float, unit: str) -> Optional[float]:
    """Convert g/mg/mcg to grams. Returns None for unsupported units."""
    unit = unit.lower()
    if unit == 'g':
        return value
    if unit == 'mg':
        return value / 1000.0
    if unit in ['mcg', 'µg', 'ug']:
        return value / 1_000_000.0
    # Unknown unit (e.g., IU). Skip aggregation for such nutrients.
    return None


def _format_mass_from_grams(value_g: float) -> Tuple[str, str]:
    """Format a gram value into a human-friendly amount string and unit."""
    if value_g >= 1.0:
        amount = round(value_g, 2)
        # Remove trailing .0 if present
        amount_str = ("%0.2f" % amount).rstrip('0').rstrip('.')
        return f"{amount_str}g", 'g'
    mg = value_g * 1000.0
    if mg >= 1.0:
        amount = round(mg, 1)
        amount_str = ("%0.1f" % amount).rstrip('0').rstrip('.')
        return f"{amount_str}mg", 'mg'
    mcg = value_g * 1_000_000.0
    amount = round(mcg)
    return f"{int(amount)}mcg", 'mcg'


def compute_meal_nutrition(detailed_menu: Dict, item_quantities: Dict[str, float]) -> Dict:
    """
    Aggregate nutrition for selected items and quantities.

    Parameters:
        detailed_menu (Dict): Output from harvard_detailed_menu_retrieve[_lite]
        item_quantities (Dict[str, float]): Mapping of item name -> quantity (servings)

    Returns:
        Dict: Aggregated nutritional report with totals and any missing items.
    """
    if not detailed_menu or 'menu' not in detailed_menu:
        return {"error": "Invalid detailed_menu structure"}

    # Build index of items by lowercase name, prefer items with fetched nutrition
    name_to_item = {}
    for category_items in detailed_menu.get('menu', {}).values():
        for item in category_items:
            if not isinstance(item, dict) or 'name' not in item:
                continue
            key = item['name'].strip().lower()
            # Prefer entries with successful nutrition
            existing = name_to_item.get(key)
            current_is_good = item.get('nutrition') is not None and item.get('nutrition_fetch_status') == 'success'
            if existing is None or (current_is_good and not (existing.get('nutrition') and existing.get('nutrition_fetch_status') == 'success')):
                name_to_item[key] = item

    totals = {
        'calories': 0.0,
        'nutrition': {}
    }
    items_aggregated = 0
    missing_items = []

    for raw_name, qty in item_quantities.items():
        if qty is None:
            continue
        try:
            qty_float = float(qty)
        except (TypeError, ValueError):
            continue
        if qty_float <= 0:
            continue

        lookup_key = str(raw_name).strip().lower()
        item = name_to_item.get(lookup_key)
        if not item:
            missing_items.append(raw_name)
            continue

        nut = item.get('nutrition') or {}
        # Calories
        calories_val = nut.get('calories')
        if isinstance(calories_val, (int, float)):
            totals['calories'] += float(calories_val) * qty_float
        else:
            # Try to coerce if it's a numeric string
            try:
                totals['calories'] += float(str(calories_val)) * qty_float
            except (TypeError, ValueError):
                pass

        # Nutrients amounts
        nutrients = (nut.get('nutrition') or {})
        for nutrient_name, nutrient_info in nutrients.items():
            amount_text = (nutrient_info or {}).get('amount')
            parsed = _parse_amount_to_value_unit(amount_text) if amount_text else None
            if not parsed:
                continue
            value, unit = parsed
            value_g = _convert_to_grams(value, unit)
            if value_g is None:
                # Skip unsupported units
                continue

            entry = totals['nutrition'].setdefault(nutrient_name, {'_grams': 0.0})
            entry['_grams'] += value_g * qty_float
        items_aggregated += 1

    # Format nutrient totals back into strings and drop helper field
    formatted_nutrition = {}
    for nutrient_name, data in totals['nutrition'].items():
        grams = data.get('_grams', 0.0)
        amount_str, unit = _format_mass_from_grams(grams)
        formatted_nutrition[nutrient_name] = {
            'amount': amount_str,
            'daily_value': None
        }

    result = {
        'metadata': detailed_menu.get('metadata', {}),
        'selections': item_quantities,
        'items_aggregated': items_aggregated,
        'missing_items': missing_items,
        'totals': {
            'calories': int(round(totals['calories'])) if totals['calories'] else 0,
            'nutrition': formatted_nutrition
        }
    }

    return result

# =============================================================================
# EXAMPLE USAGE AND TESTING
# =============================================================================

if __name__ == "__main__":
    # Test with a sample URL (you would replace this with an actual menu URL)
    test_url = "https://www.foodpro.huds.harvard.edu/foodpro/longmenucopy.aspx?sName=HARVARD+UNIVERSITY+DINING+SERVICES&locationNum=30&locationName=Dining+Hall&naFlag=1&WeeksMenus=This+Week%27s+Menus&dtdate=9%2f29%2f2025&mealName=Breakfast+Menu"
    
    print("Testing basic menu parser...")
    basic_result = harvard_dining_menu_retrieve(test_url)
    print(_format_json_output(basic_result))
    
    print("\n" + "="*60)
    print("Testing lite detailed menu parser...")
    lite_result = harvard_detailed_menu_retrieve_lite(test_url, max_items_per_category=2)
    
    if "error" not in lite_result:
        save_detailed_menu_to_file(lite_result, "sample_detailed_menu_lite.json")
        print("\nLite test completed successfully!")
        
        # Uncomment the line below to test the full version (will take longer)
        # full_result = harvard_detailed_menu_retrieve(test_url)
        # save_detailed_menu_to_file(full_result, "sample_detailed_menu_full.json")
    else:
        print(f"Error: {lite_result['error']}")
