"""
Navigable help system for Accessible Space Atlas.

Provides two help modes:
- KeystrokeHelp (H key): Quick reference for keyboard shortcuts
- EducationalHelp (Shift+H): Educational content about space
"""

from dataclasses import dataclass
from typing import List
import queue


@dataclass
class HelpItem:
    """A single help item with title and description."""
    title: str
    description: str


class HelpNavigator:
    """Base class for navigable help content."""

    def __init__(self, speech_queue: queue.Queue, config_manager):
        """
        Initialize help navigator.

        Args:
            speech_queue: Queue for speech output
            config_manager: ConfigManager for settings
        """
        self.speech_queue = speech_queue
        self.config_manager = config_manager
        self.items: List[HelpItem] = []
        self._index: int = 0
        self._title: str = "Help"
        self._build_items()

    def _build_items(self) -> None:
        """Build help items list. Override in subclasses."""
        pass

    def announce_entry(self) -> None:
        """Announce help mode entry."""
        self.speech_queue.put(
            f"{self._title}. {len(self.items)} items. "
            "Use up and down arrows to browse, Enter to read details, Escape to exit."
        )
        self._announce_current_title()

    def move_up(self) -> None:
        """Move to previous help item (with wrap)."""
        if self._index > 0:
            self._index -= 1
        else:
            self._index = len(self.items) - 1
        self._announce_current_title()

    def move_down(self) -> None:
        """Move to next help item (with wrap)."""
        if self._index < len(self.items) - 1:
            self._index += 1
        else:
            self._index = 0
        self._announce_current_title()

    def read_current(self) -> None:
        """Read full description of current item."""
        if not self.items:
            return
        item = self.items[self._index]
        self.speech_queue.put(f"{item.title}. {item.description}")

    def _announce_current_title(self) -> None:
        """Announce current item title and position."""
        if not self.items:
            self.speech_queue.put("No help items available.")
            return
        item = self.items[self._index]
        position = f"{self._index + 1} of {len(self.items)}"
        self.speech_queue.put(f"{item.title}, {position}")


class KeystrokeHelp(HelpNavigator):
    """Navigable keyboard shortcut help (H key)."""

    def _build_items(self) -> None:
        """Build keystroke help items."""
        self._title = "Keyboard Shortcuts"
        self.items = [
            # Navigation
            HelpItem(
                "Arrow Keys",
                "Navigate spatially between celestial objects. Move to the nearest object in the direction you press."
            ),
            HelpItem(
                "J - Tree Navigation",
                "Open hierarchical tree view. Browse objects by orbital hierarchy or by type. Use arrows to navigate, Enter to select, Left to go back."
            ),
            HelpItem(
                "S - Search",
                "Search for objects by name. Type your search query and press Enter to find matching objects."
            ),
            HelpItem(
                "F - Filter",
                "Cycle through object type filters. Show only planets, moons, asteroids, or all objects."
            ),

            # Modes and Settings
            HelpItem(
                "M - Mode",
                "Cycle through user modes. Educational mode gives detailed explanations, Exploration mode is balanced, Advanced mode is concise."
            ),
            HelpItem(
                "T - Time Scale",
                "Change the time scale for orbital motion simulation. Higher values speed up planetary movement."
            ),
            HelpItem(
                "P - Pause",
                "Pause or resume dynamic orbital positions. When paused, objects stay fixed."
            ),
            HelpItem(
                "O - Audio Mode",
                "Toggle between hierarchical and true scale audio positioning. Hierarchical mode groups moons near their planets."
            ),
            HelpItem(
                "U - Units",
                "Cycle distance units between astronomical units, kilometers, and miles."
            ),

            # Bookmarks
            HelpItem(
                "B - Bookmark",
                "Bookmark the currently selected object. You can recall it later with number keys."
            ),
            HelpItem(
                "Number Keys 0-9",
                "Recall bookmarked objects. Keys 1 through 9 recall slots 1-9, key 0 recalls slot 10."
            ),
            HelpItem(
                "Shift + Number",
                "Save current object to a specific bookmark slot. Shift+1 saves to slot 1, and so on."
            ),
            HelpItem(
                "Shift + B",
                "List all your current bookmarks with their slot numbers."
            ),

            # Information
            HelpItem(
                "V - Velocity",
                "Announce the current object's velocity in kilometers per second."
            ),
            HelpItem(
                "R - Distance",
                "Announce the distance from the current object to your reference object."
            ),
            HelpItem(
                "Shift + R",
                "Set the current object as your distance reference for relative measurements."
            ),
            HelpItem(
                "W - Weather",
                "Check current space weather conditions including solar flares and geomagnetic storms."
            ),
            HelpItem(
                "A - Ambient Audio",
                "Toggle ambient space audio. When enabled, hear real recordings from spacecraft like plasma waves from Jupiter or Earth's magnetosphere. Audio changes when you navigate to different objects."
            ),

            # View Controls
            HelpItem(
                "Page Up",
                "Zoom in on the visualization, making objects appear closer together."
            ),
            HelpItem(
                "Page Down",
                "Zoom out on the visualization, spreading objects further apart."
            ),
            HelpItem(
                "Home",
                "Reset zoom level to 100 percent."
            ),
            HelpItem(
                "L - Follow",
                "Toggle follow mode to lock the camera on the selected object."
            ),
            HelpItem(
                "C - Cluster",
                "Focus on a planetary system. Amplifies the audio of moons and spacecraft orbiting the selected planet."
            ),

            # Audio
            HelpItem(
                "Minus Key",
                "Decrease master volume by 10 percent."
            ),
            HelpItem(
                "Equals Key",
                "Increase master volume by 10 percent."
            ),

            # Data
            HelpItem(
                "E - Export",
                "Export all celestial object data to a CSV file for external analysis."
            ),

            # Tree Navigation (when in tree mode)
            HelpItem(
                "In Tree: Tab",
                "Flatten the current category into a simple list for easier browsing."
            ),
            HelpItem(
                "In Tree: Shift+Tab",
                "Return from flattened list back to the hierarchical tree view."
            ),

            # Help and Exit
            HelpItem(
                "H - Keystroke Help",
                "Open this keyboard shortcuts help navigator."
            ),
            HelpItem(
                "Shift + H - Educational Help",
                "Open educational content about space and celestial objects."
            ),
            HelpItem(
                "Escape",
                "Exit the current mode. Closes help, tree navigation, or search mode."
            ),
        ]


class EducationalHelp(HelpNavigator):
    """Navigable educational content about space (Shift+H key)."""

    def _build_items(self) -> None:
        """Build educational help items."""
        self._title = "Learn About Space"
        self.items = [
            HelpItem(
                "What is Space?",
                "Space is the vast, nearly empty expanse that exists beyond Earth's atmosphere. "
                "It begins about 100 kilometers above sea level at the Karman line. "
                "Space is not completely empty - it contains gas, dust, radiation, and countless celestial objects."
            ),
            HelpItem(
                "The Solar System",
                "Our solar system formed about 4.6 billion years ago from a giant cloud of gas and dust. "
                "It consists of the Sun at the center, eight planets, dwarf planets, moons, asteroids, and comets. "
                "The Sun contains 99.8 percent of the solar system's total mass."
            ),
            HelpItem(
                "Orbital Mechanics",
                "Objects in space orbit due to the balance between their velocity and gravitational attraction. "
                "The closer an object is to the Sun, the faster it must move to maintain a stable orbit. "
                "Mercury orbits the Sun in just 88 days, while Neptune takes 165 years."
            ),
            HelpItem(
                "The Planets",
                "The eight planets are divided into two groups. The inner rocky planets are Mercury, Venus, Earth, and Mars. "
                "The outer gas giants are Jupiter, Saturn, Uranus, and Neptune. "
                "Jupiter is so massive that it could contain all other planets combined with room to spare."
            ),
            HelpItem(
                "Moons",
                "Moons are natural satellites that orbit planets. Earth has one moon, but Jupiter has over 90 known moons. "
                "Many moons are tidally locked, meaning the same side always faces their planet. "
                "Some moons like Europa and Enceladus may have liquid water oceans beneath their icy surfaces."
            ),
            HelpItem(
                "Asteroids and Comets",
                "Asteroids are rocky objects mostly found in the asteroid belt between Mars and Jupiter. "
                "Comets are icy bodies from the outer solar system that develop tails when approaching the Sun. "
                "Both are remnants from the early solar system that never formed into planets."
            ),
            HelpItem(
                "Dwarf Planets",
                "Dwarf planets are large enough to be round but haven't cleared their orbital neighborhood of debris. "
                "Pluto was reclassified as a dwarf planet in 2006. Other dwarf planets include Ceres, Eris, Makemake, and Haumea. "
                "Many dwarf planets exist in the Kuiper Belt beyond Neptune's orbit."
            ),
            HelpItem(
                "Spacecraft Exploration",
                "Humans have sent spacecraft throughout the solar system since the 1960s. "
                "Voyager 1 and 2 have left the solar system and continue transmitting from interstellar space. "
                "Rovers like Perseverance explore Mars, while missions like Juno study Jupiter up close."
            ),
            HelpItem(
                "Distances in Space",
                "Distances in space are measured in astronomical units (AU), where 1 AU equals Earth's distance from the Sun. "
                "Light travels at about 300,000 kilometers per second, yet takes over 4 hours to reach Neptune. "
                "The nearest star, Proxima Centauri, is 4.24 light-years away, meaning its light takes over 4 years to reach us."
            ),
            HelpItem(
                "Space Weather",
                "Space weather refers to conditions in space caused by solar activity. "
                "Solar flares release bursts of radiation, while coronal mass ejections send plasma into space. "
                "Strong space weather can disrupt satellites, GPS, and power grids on Earth, and create beautiful auroras."
            ),
            HelpItem(
                "The Sun",
                "The Sun is a medium-sized star about 4.6 billion years old, roughly halfway through its life. "
                "It is a ball of hot plasma primarily composed of hydrogen and helium. "
                "The Sun's core reaches temperatures of 15 million degrees Celsius, where nuclear fusion converts hydrogen to helium."
            ),
            HelpItem(
                "Gravity in Space",
                "Gravity is the force that shapes the universe, keeping planets in orbit and forming galaxies. "
                "Objects in orbit experience continuous free-fall, creating the sensation of weightlessness. "
                "The strength of gravity decreases with distance, following an inverse square law."
            ),
        ]
