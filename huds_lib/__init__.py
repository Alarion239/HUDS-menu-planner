"""
HUDS (Harvard University Dining Services) Menu Parser

A Python package for retrieving and parsing Harvard dining menu data.
"""

from .parser import (
    harvard_dining_menu_retrieve,
    harvard_nutrition_label_retrieve,
    harvard_detailed_menu_retrieve,
    harvard_detailed_menu_retrieve_lite,
    save_detailed_menu_to_file
)
from .webpage import harvard_dining_menu_url
from .model import create_meal


__version__ = "0.1.0"
__author__ = "HUDS Parser Team"

__all__ = [
    "harvard_dining_menu_retrieve",
    "harvard_nutrition_label_retrieve",
    "harvard_detailed_menu_retrieve",
    "harvard_detailed_menu_retrieve_lite",
    "save_detailed_menu_to_file",
    "harvard_dining_menu_url",
    "create_meal",
    "HUDSFormAutomation",
    "huds_nutrition_form_submit",
    "parse_nutritive_report",
    "select_report_section"
]
