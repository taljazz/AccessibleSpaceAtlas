"""
Configuration manager for user preferences and modes.
Handles three user experience modes: Educational, Exploration, and Advanced.
"""
import json
import logging
import sys
import os
from enum import Enum
from pathlib import Path


def get_base_path():
    """Get the base path for data files, handling both dev and compiled scenarios."""
    if getattr(sys, 'frozen', False) or '__compiled__' in dir():
        return Path(os.path.dirname(sys.executable))
    else:
        return Path(__file__).parent.parent


class UserMode(Enum):
    """User experience modes."""
    EDUCATIONAL = "educational"    # Verbose, guided, simple audio
    EXPLORATION = "exploration"    # Balanced (default)
    ADVANCED = "advanced"          # Concise, technical, full 3D audio


class DistanceUnit(Enum):
    """Distance unit options."""
    AU = "au"           # Astronomical Units (default)
    KM = "km"           # Kilometers
    MILES = "miles"     # Miles


class ConfigManager:
    """Manages user preferences and mode-specific settings."""

    # Conversion constants
    AU_TO_KM = 149597870.7
    AU_TO_MILES = 92955807.3
    AU_PER_DAY_TO_KM_PER_SEC = AU_TO_KM / 86400  # Convert AU/day to km/s

    def __init__(self, config_file="config.json"):
        base_path = get_base_path()
        self.config_file = base_path / config_file
        self.user_mode = UserMode.EXPLORATION  # Default mode
        self.time_scale = 365.0  # Days per second (default: 1 year per second)
        self.dynamic_positions = True  # Enable dynamic position updates
        self.distance_unit = DistanceUnit.AU  # Default distance unit
        self.bookmarks = {}  # Persistent bookmarks: {slot_number: object_name}
        self.zoom_level = 1.0  # Visualization zoom (0.1 to 10.0)
        self.master_volume = 1.0  # Master volume (0.0 to 1.0)

        # Mode-specific configurations
        self.mode_configs = {
            UserMode.EDUCATIONAL: {
                'announcement_verbosity': 'verbose',
                'help_level': 'detailed',
                'sound_complexity': 'simple',
                'audio_cues': True,
                'show_hints': True,
            },
            UserMode.EXPLORATION: {
                'announcement_verbosity': 'balanced',
                'help_level': 'moderate',
                'sound_complexity': 'moderate',
                'audio_cues': True,
                'show_hints': False,
            },
            UserMode.ADVANCED: {
                'announcement_verbosity': 'concise',
                'help_level': 'minimal',
                'sound_complexity': 'complex',
                'audio_cues': False,
                'show_hints': False,
            }
        }

        # Load saved preferences if they exist
        self.load_preferences()

    def get_current_config(self):
        """Get the configuration for the current mode."""
        return self.mode_configs[self.user_mode]

    def format_distance(self, distance_au):
        """
        Format distance in the current unit.

        Args:
            distance_au: Distance in AU

        Returns:
            Formatted distance string with unit
        """
        if self.distance_unit == DistanceUnit.AU:
            # Space between A and U so screen readers don't say "Australian dollars"
            return f"{distance_au:.2f} A U"
        elif self.distance_unit == DistanceUnit.KM:
            distance_km = distance_au * self.AU_TO_KM
            if distance_km >= 1e9:
                return f"{distance_km / 1e9:.2f} billion km"
            elif distance_km >= 1e6:
                return f"{distance_km / 1e6:.2f} million km"
            else:
                return f"{distance_km:,.0f} km"
        else:  # MILES
            distance_miles = distance_au * self.AU_TO_MILES
            if distance_miles >= 1e9:
                return f"{distance_miles / 1e9:.2f} billion miles"
            elif distance_miles >= 1e6:
                return f"{distance_miles / 1e6:.2f} million miles"
            else:
                return f"{distance_miles:,.0f} miles"

    def format_speed(self, vx, vy, vz):
        """
        Format speed from velocity components.

        Args:
            vx, vy, vz: Velocity components in AU/day

        Returns:
            Formatted speed string
        """
        # Calculate speed magnitude in AU/day
        speed_au_day = (vx**2 + vy**2 + vz**2) ** 0.5

        # Convert to km/s (more intuitive)
        speed_km_s = speed_au_day * self.AU_PER_DAY_TO_KM_PER_SEC

        if speed_km_s >= 1000:
            return f"{speed_km_s / 1000:.2f} thousand km/s"
        elif speed_km_s >= 1:
            return f"{speed_km_s:.2f} km/s"
        else:
            return f"{speed_km_s * 1000:.1f} m/s"

    def cycle_distance_unit(self):
        """Cycle through distance units: AU -> km -> miles -> AU."""
        units = [DistanceUnit.AU, DistanceUnit.KM, DistanceUnit.MILES]
        current_index = units.index(self.distance_unit)
        next_index = (current_index + 1) % len(units)
        self.distance_unit = units[next_index]
        self.save_preferences()
        return self.distance_unit

    def get_distance_unit_name(self):
        """Get human-readable name for current distance unit."""
        names = {
            DistanceUnit.AU: "Astronomical Units",  # Full name for announcements
            DistanceUnit.KM: "Kilometers",
            DistanceUnit.MILES: "Miles"
        }
        return names[self.distance_unit]

    def get_distance_unit_short(self):
        """Get short unit name for display (screen reader safe)."""
        names = {
            DistanceUnit.AU: "A U",  # Spaced for screen readers
            DistanceUnit.KM: "km",
            DistanceUnit.MILES: "mi"
        }
        return names[self.distance_unit]

    def get_announcement_template(self, celestial_object):
        """
        Get mode-specific announcement template for a celestial object.

        Args:
            celestial_object: CelestialObject instance

        Returns:
            Formatted announcement string based on current mode
        """
        verbosity = self.get_current_config()['announcement_verbosity']
        distance_str = self.format_distance(celestial_object.distance)

        if verbosity == 'verbose':
            # Educational mode: Detailed, explanatory
            type_descriptions = {
                "Planet": "Planets are large celestial bodies that orbit stars.",
                "Dwarf Planet": "Dwarf planets are celestial bodies similar to planets but smaller.",
                "Asteroid": "Asteroids are rocky objects that orbit the Sun.",
                "Comet": "Comets are icy objects that develop tails when near the Sun.",
                "Spacecraft": "Spacecraft are human-made vehicles exploring space.",
            }

            description = type_descriptions.get(celestial_object.type, "This is a celestial object.")

            announcement = (
                f"This is a {celestial_object.type} named {celestial_object.name}. "
                f"{description} "
                f"It is located {distance_str} from the Sun. "
                f"Use arrow keys to explore nearby objects, or press J to open the jump menu."
            )

        elif verbosity == 'balanced':
            # Exploration mode: Current behavior (moderate)
            announcement = (
                f"{celestial_object.type}: {celestial_object.name}, "
                f"Distance: {distance_str}."
            )

        else:  # concise
            # Advanced mode: Minimal, technical
            announcement = (
                f"{celestial_object.name}, "
                f"{distance_str}, "
                f"{celestial_object.type}"
            )

        return announcement

    def get_selection_announcement(self, celestial_object):
        """Get announcement for when an object is selected in jump mode."""
        verbosity = self.get_current_config()['announcement_verbosity']
        distance_str = self.format_distance(celestial_object.distance)

        if verbosity == 'verbose':
            return (
                f"Selected: {celestial_object.type} {celestial_object.name}. "
                f"Distance: {distance_str}. "
                f"Press Enter to jump to this object."
            )
        elif verbosity == 'balanced':
            return (
                f"Selected: {celestial_object.type} {celestial_object.name}, "
                f"Distance: {distance_str}."
            )
        else:  # concise
            return f"{celestial_object.name}, {distance_str}"

    def get_velocity_announcement(self, celestial_object):
        """
        Get announcement for object's velocity.

        Args:
            celestial_object: CelestialObject instance

        Returns:
            Formatted velocity announcement string
        """
        speed_str = self.format_speed(
            celestial_object.vx,
            celestial_object.vy,
            celestial_object.vz
        )

        verbosity = self.get_current_config()['announcement_verbosity']

        if verbosity == 'verbose':
            return f"{celestial_object.name} is traveling at {speed_str} through space."
        elif verbosity == 'balanced':
            return f"{celestial_object.name} speed: {speed_str}."
        else:  # concise
            return f"{celestial_object.name}: {speed_str}"

    def get_relative_distance_announcement(self, obj1, obj2):
        """
        Get announcement for distance between two objects.

        Args:
            obj1: First CelestialObject
            obj2: Second CelestialObject

        Returns:
            Formatted relative distance announcement
        """
        # Calculate distance between objects
        dx = obj1.x - obj2.x
        dy = obj1.y - obj2.y
        dz = obj1.z - obj2.z
        distance_au = (dx**2 + dy**2 + dz**2) ** 0.5

        distance_str = self.format_distance(distance_au)

        verbosity = self.get_current_config()['announcement_verbosity']

        if verbosity == 'verbose':
            return f"{obj1.name} is {distance_str} away from {obj2.name}."
        elif verbosity == 'balanced':
            return f"Distance from {obj1.name} to {obj2.name}: {distance_str}."
        else:  # concise
            return f"{obj1.name} to {obj2.name}: {distance_str}"

    def get_audio_params(self):
        """
        Get audio generation parameters based on current mode.

        Returns:
            Dictionary with audio configuration
        """
        complexity = self.get_current_config()['sound_complexity']

        return {
            'complexity': complexity,
            'enable_stereo': complexity in ['moderate', 'complex'],
            'enable_depth_effects': complexity == 'complex',
            'enable_reverb': complexity == 'complex',
        }

    def cycle_mode(self):
        """Cycle through user modes: Educational -> Exploration -> Advanced -> Educational."""
        modes = [UserMode.EDUCATIONAL, UserMode.EXPLORATION, UserMode.ADVANCED]
        current_index = modes.index(self.user_mode)
        next_index = (current_index + 1) % len(modes)
        self.user_mode = modes[next_index]

        # Save preference
        self.save_preferences()

        return self.user_mode

    def get_mode_change_announcement(self):
        """Get announcement text for mode change."""
        mode_descriptions = {
            UserMode.EDUCATIONAL: (
                "Educational mode activated. "
                "Detailed descriptions enabled. "
                "Perfect for learning about space objects."
            ),
            UserMode.EXPLORATION: (
                "Exploration mode activated. "
                "Balanced information display. "
                "Ideal for browsing the solar system."
            ),
            UserMode.ADVANCED: (
                "Advanced mode activated. "
                "Concise technical information. "
                "For experienced users."
            ),
        }

        return mode_descriptions.get(self.user_mode, f"{self.user_mode.value.capitalize()} mode activated.")

    def get_jump_mode_activation_announcement(self):
        """Get announcement for when jump mode is activated."""
        help_level = self.get_current_config()['help_level']

        if help_level == 'detailed':
            return (
                "Jump mode activated. "
                "This mode lets you browse all objects in a list. "
                "Use up and down arrow keys to navigate through objects. "
                "Press Enter to select an object and jump to it. "
                "Press Escape to cancel and return to spatial navigation."
            )
        elif help_level == 'moderate':
            return (
                "Jump mode activated. "
                "Use arrow keys to navigate the list and press Enter to select."
            )
        else:  # minimal
            return "Jump mode."

    def cycle_time_scale(self):
        """Cycle through time scale presets."""
        time_scales = [1.0, 10.0, 30.0, 100.0, 365.0, 1000.0]  # Days per second
        current_index = min(range(len(time_scales)), key=lambda i: abs(time_scales[i] - self.time_scale))
        next_index = (current_index + 1) % len(time_scales)
        self.time_scale = time_scales[next_index]
        self.save_preferences()
        return self.time_scale

    def toggle_dynamic_positions(self):
        """Toggle dynamic position updates on/off."""
        self.dynamic_positions = not self.dynamic_positions
        self.save_preferences()
        return self.dynamic_positions

    def get_time_scale_description(self):
        """Get human-readable description of current time scale."""
        if self.time_scale >= 365:
            years = self.time_scale / 365.0
            return f"{years:.1f} year{'s' if years != 1 else ''} per second"
        elif self.time_scale >= 30:
            months = self.time_scale / 30.0
            return f"{months:.1f} month{'s' if months != 1 else ''} per second"
        elif self.time_scale >= 1:
            return f"{self.time_scale:.0f} day{'s' if self.time_scale != 1 else ''} per second"
        else:
            hours = self.time_scale * 24
            return f"{hours:.1f} hour{'s' if hours != 1 else ''} per second"

    def save_preferences(self):
        """Save current preferences to config file."""
        try:
            config_data = {
                'user_mode': self.user_mode.value,
                'time_scale': self.time_scale,
                'dynamic_positions': self.dynamic_positions,
                'distance_unit': self.distance_unit.value,
                'bookmarks': self.bookmarks,  # {slot: object_name}
                'zoom_level': self.zoom_level,
                'master_volume': self.master_volume,
            }

            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=2)

            logging.info(f"Preferences saved to {self.config_file}")
        except Exception as e:
            logging.error(f"Failed to save preferences: {e}")

    def load_preferences(self):
        """Load preferences from config file if it exists."""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)

                # Load user mode
                mode_value = config_data.get('user_mode', 'exploration')
                try:
                    self.user_mode = UserMode(mode_value)
                    logging.info(f"Loaded preferences: mode={self.user_mode.value}")
                except ValueError:
                    logging.warning(f"Invalid mode '{mode_value}' in config, using default")
                    self.user_mode = UserMode.EXPLORATION

                # Load time scale
                self.time_scale = config_data.get('time_scale', 365.0)

                # Load dynamic positions setting
                self.dynamic_positions = config_data.get('dynamic_positions', True)

                # Load distance unit
                unit_value = config_data.get('distance_unit', 'au')
                try:
                    self.distance_unit = DistanceUnit(unit_value)
                except ValueError:
                    self.distance_unit = DistanceUnit.AU

                # Load bookmarks (convert string keys to int)
                raw_bookmarks = config_data.get('bookmarks', {})
                self.bookmarks = {int(k): v for k, v in raw_bookmarks.items()}

                # Load zoom level
                self.zoom_level = config_data.get('zoom_level', 1.0)

                # Load master volume
                self.master_volume = config_data.get('master_volume', 1.0)

                logging.info(f"Time scale: {self.time_scale} days/sec, Dynamic: {self.dynamic_positions}")
                logging.info(f"Distance unit: {self.distance_unit.value}, Zoom: {self.zoom_level}")
                if self.bookmarks:
                    logging.info(f"Loaded {len(self.bookmarks)} bookmarks")
        except Exception as e:
            logging.error(f"Failed to load preferences: {e}")
            # Continue with defaults

    # Bookmark management methods
    def add_bookmark(self, slot, object_name):
        """
        Add or update a bookmark.

        Args:
            slot: Bookmark slot number (1-9, or 0 for slot 10)
            object_name: Name of celestial object to bookmark

        Returns:
            True if bookmark was added, False if slot invalid
        """
        if 0 <= slot <= 9:
            self.bookmarks[slot] = object_name
            self.save_preferences()
            return True
        return False

    def get_bookmark(self, slot):
        """
        Get bookmarked object name.

        Args:
            slot: Bookmark slot number

        Returns:
            Object name or None if slot empty
        """
        return self.bookmarks.get(slot)

    def clear_bookmark(self, slot):
        """Clear a bookmark slot."""
        if slot in self.bookmarks:
            del self.bookmarks[slot]
            self.save_preferences()
            return True
        return False

    def get_next_available_slot(self):
        """Get next available bookmark slot (1-9, then 0)."""
        for i in range(1, 10):
            if i not in self.bookmarks:
                return i
        if 0 not in self.bookmarks:
            return 0
        return None  # All slots full

    # Zoom control methods
    def zoom_in(self, factor=1.25):
        """
        Zoom in (increase scale).

        Args:
            factor: Zoom multiplier (default 1.25 = 25% zoom in)

        Returns:
            New zoom level
        """
        self.zoom_level = min(10.0, self.zoom_level * factor)
        self.save_preferences()
        return self.zoom_level

    def zoom_out(self, factor=1.25):
        """
        Zoom out (decrease scale).

        Args:
            factor: Zoom divisor (default 1.25 = 20% zoom out)

        Returns:
            New zoom level
        """
        self.zoom_level = max(0.1, self.zoom_level / factor)
        self.save_preferences()
        return self.zoom_level

    def reset_zoom(self):
        """Reset zoom to default (1.0)."""
        self.zoom_level = 1.0
        self.save_preferences()
        return self.zoom_level

    def get_zoom_description(self):
        """Get human-readable zoom level description."""
        percentage = int(self.zoom_level * 100)
        return f"{percentage}% zoom"

    # Master volume methods (for persistence)
    def set_master_volume(self, volume):
        """Set master volume (0.0 to 1.0)."""
        self.master_volume = max(0.0, min(1.0, volume))
        self.save_preferences()
        return self.master_volume

    def get_mode_indicator_text(self):
        """Get text for displaying current mode in UI."""
        mode_names = {
            UserMode.EDUCATIONAL: "Educational",
            UserMode.EXPLORATION: "Exploration",
            UserMode.ADVANCED: "Advanced",
        }
        return f"Mode: {mode_names[self.user_mode]}"
