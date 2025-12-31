"""
Celestial object database and catalog.
Loads from JSON catalog and supports dynamic querying of NASA APIs.
"""
import json
import logging
import sys
import os
from pathlib import Path


def get_base_path():
    """Get the base path for data files, handling both dev and compiled scenarios."""
    # Check if running as compiled Nuitka executable
    if getattr(sys, 'frozen', False) or '__compiled__' in dir():
        # Running as compiled - use executable directory
        return Path(os.path.dirname(sys.executable))
    else:
        # Running as script - use script directory
        return Path(__file__).parent.parent


class CelestialDatabase:
    """Manages celestial object definitions and catalog with dynamic loading."""

    def __init__(self, catalog_file="data/celestial_objects.json"):
        # Get correct base path for both dev and compiled modes
        base_path = get_base_path()
        self.catalog_file = base_path / catalog_file
        self.catalog_data = None
        self.definitions = []
        self.active_categories = ["star", "planets", "dwarf_planets", "moons", "spacecraft"]  # Default categories
        self._load_catalog()

    def _load_catalog(self):
        """Load celestial objects from JSON catalog file."""
        try:
            if self.catalog_file.exists():
                with open(self.catalog_file, 'r', encoding='utf-8') as f:
                    self.catalog_data = json.load(f)

                logging.info(f"Loaded catalog version {self.catalog_data.get('version', 'unknown')}")
                logging.info(f"Last updated: {self.catalog_data.get('last_updated', 'unknown')}")

                # Load objects from active categories
                self._load_active_categories()
            else:
                logging.warning(f"Catalog file not found: {self.catalog_file}")
                # Fall back to minimal set
                self.definitions = self._get_fallback_definitions()
        except Exception as e:
            logging.error(f"Error loading catalog: {e}")
            self.definitions = self._get_fallback_definitions()

    def _load_active_categories(self):
        """Load objects from currently active categories."""
        self.definitions = []
        categories = self.catalog_data.get('categories', {})

        for category in self.active_categories:
            if category in categories:
                objects = categories[category]
                # Add quotes around command codes for API compatibility
                for obj in objects:
                    obj_copy = obj.copy()
                    # Ensure command has quotes
                    if not obj_copy['command'].startswith("'"):
                        obj_copy['command'] = f"'{obj_copy['command']}'"
                    self.definitions.append(obj_copy)

        logging.info(f"Loaded {len(self.definitions)} objects from categories: {', '.join(self.active_categories)}")

    def _get_fallback_definitions(self):
        """Return minimal fallback definitions if JSON loading fails."""
        return [
            {"name": "Mercury", "command": "'199'", "type": "Planet", "size": 8},
            {"name": "Venus", "command": "'299'", "type": "Planet", "size": 10},
            {"name": "Earth", "command": "'399'", "type": "Planet", "size": 12},
            {"name": "Mars", "command": "'499'", "type": "Planet", "size": 9},
            {"name": "Jupiter", "command": "'599'", "type": "Planet", "size": 15},
            {"name": "Saturn", "command": "'699'", "type": "Planet", "size": 14},
            {"name": "Uranus", "command": "'799'", "type": "Planet", "size": 13},
            {"name": "Neptune", "command": "'899'", "type": "Planet", "size": 13},
        ]

    def get_all_objects(self):
        """Get all loaded celestial object definitions."""
        return self.definitions

    def get_objects_by_type(self, obj_type):
        """
        Filter objects by type (Planet, Moon, Asteroid, Comet, Spacecraft, etc.).

        Args:
            obj_type: Type string to filter by

        Returns:
            List of objects matching the type
        """
        return [obj for obj in self.definitions if obj["type"] == obj_type]

    def get_objects_by_category(self, category):
        """
        Get all objects from a specific category.

        Args:
            category: Category name (planets, moons, asteroids, comets, spacecraft, dwarf_planets)

        Returns:
            List of objects in that category
        """
        if not self.catalog_data:
            return []

        categories = self.catalog_data.get('categories', {})
        if category in categories:
            objects = categories[category]
            # Add quotes to command codes
            result = []
            for obj in objects:
                obj_copy = obj.copy()
                if not obj_copy['command'].startswith("'"):
                    obj_copy['command'] = f"'{obj_copy['command']}'"
                result.append(obj_copy)
            return result
        return []

    def search_by_name(self, search_term):
        """
        Search for objects by name (case-insensitive, partial match).

        Args:
            search_term: String to search for in object names

        Returns:
            List of matching objects
        """
        search_lower = search_term.lower()
        return [obj for obj in self.definitions if search_lower in obj["name"].lower()]

    def set_active_categories(self, categories):
        """
        Set which categories to load.

        Args:
            categories: List of category names to activate
        """
        self.active_categories = categories
        self._load_active_categories()
        logging.info(f"Active categories set to: {', '.join(categories)}")

    def add_category(self, category):
        """
        Add a category to the active list.

        Args:
            category: Category name to add
        """
        if category not in self.active_categories:
            self.active_categories.append(category)
            self._load_active_categories()
            logging.info(f"Added category: {category}")

    def remove_category(self, category):
        """
        Remove a category from the active list.

        Args:
            category: Category name to remove
        """
        if category in self.active_categories:
            self.active_categories.remove(category)
            self._load_active_categories()
            logging.info(f"Removed category: {category}")

    def get_available_categories(self):
        """Get list of all available categories in the catalog."""
        if not self.catalog_data:
            return []
        return list(self.catalog_data.get('categories', {}).keys())

    def get_catalog_info(self):
        """Get metadata about the loaded catalog."""
        if not self.catalog_data:
            return None

        return {
            'version': self.catalog_data.get('version'),
            'last_updated': self.catalog_data.get('last_updated'),
            'total_objects': self.catalog_data.get('metadata', {}).get('total_objects', 0),
            'categories': self.catalog_data.get('metadata', {}).get('categories_count', {}),
            'active_categories': self.active_categories,
            'loaded_objects': len(self.definitions)
        }

    def add_custom_object(self, name, command, type_, size, description=""):
        """
        Add a custom object to the database.

        Args:
            name: Object name
            command: Horizons API command code
            type_: Object type
            size: Display size
            description: Optional description
        """
        # Ensure command has quotes
        if not command.startswith("'"):
            command = f"'{command}'"

        self.definitions.append({
            "name": name,
            "command": command,
            "type": type_,
            "size": size,
            "description": description
        })
        logging.info(f"Added custom object: {name}")

    def get_statistics(self):
        """Get statistics about loaded objects."""
        stats = {
            'total': len(self.definitions),
            'by_type': {}
        }

        for obj in self.definitions:
            obj_type = obj['type']
            stats['by_type'][obj_type] = stats['by_type'].get(obj_type, 0) + 1

        return stats
