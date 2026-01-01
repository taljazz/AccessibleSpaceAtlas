import pygame
import sys
import threading
import time
import queue
import logging
from pygame.locals import *

# Import extracted modules
from ui.speech_handler import SpeechHandler, cytolk_available, tolk
from models.celestial_object import CelestialObject
from models.celestial_database import CelestialDatabase
from engine.navigation_controller import NavigationController
from engine.config_manager import ConfigManager, UserMode, DistanceUnit
from engine.audio_engine import AudioEngine
from utils.api_client import HorizonsAPIClient
from utils.space_weather_client import SpaceWeatherClient
from navigation.tree_mode import TreeNavigator
from ui.help_navigator import KeystrokeHelp, EducationalHelp
from engine.ambient_audio_manager import AmbientAudioManager

# For CSV export
import csv
import os

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Initialize Pygame before defining CelestialObject
pygame.init()
pygame.mixer.init()

# Screen settings
WIDTH, HEIGHT = 1200, 800
SCREEN = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Accessible Audio Space Atlas")

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
STAR_COLOR = (255, 255, 0)          # Bright Yellow
PLANET_COLOR = (100, 149, 237)      # Cornflower Blue
DWARF_PLANET_COLOR = (147, 112, 219) # Medium Purple
MOON_COLOR = (192, 192, 192)        # Silver
ASTEROID_COLOR = (169, 169, 169)    # Dark Gray
COMET_COLOR = (255, 215, 0)         # Gold
SPACECRAFT_COLOR = (255, 69, 0)     # Orange Red

# Font for displaying text (optional visual feedback)
FONT = pygame.font.SysFont("Arial", 16)

# Selection mode flag (legacy - replaced by tree mode)
selection_mode = False

# Index for list navigation (legacy - replaced by tree mode)
selection_index = 0

# Tree navigation mode (replaces flat jump mode)
tree_mode = False
tree_navigator = None

# Help navigation mode
help_mode = False
help_navigator = None

# Object filter mode
filter_mode = "all"  # Options: "all", "Star", "Planet", "Dwarf Planet", "Moon", "Asteroid", "Comet", "Spacecraft"
filter_types = ["all", "Star", "Planet", "Dwarf Planet", "Moon", "Asteroid", "Comet", "Spacecraft"]

# Search mode
search_mode = False
search_query = ""

# Bookmarks are now managed by ConfigManager for persistence
# Reference object for relative distance (default: Earth)
reference_object_name = "Earth"

# Follow mode (camera locked on object)
follow_mode = False
followed_object = None

# Cluster focus mode (amplify sounds of children objects)
cluster_focus_mode = False
focused_parent = None

# Audio positioning mode (hierarchical vs true scale)
hierarchical_audio_mode = True  # True = orbital relationships, False = raw AU distances

# Master volume control
master_volume = 1.0  # 0.0 to 1.0, in 0.1 increments

# CelestialObject class is now imported from models.celestial_object

def announce_current_selection(celestial_objects, index, speech_queue, config_manager):
    if 0 <= index < len(celestial_objects):
        obj = celestial_objects[index]
        announcement = config_manager.get_selection_announcement(obj)
        speech_queue.put(announcement)

def filter_objects(celestial_objects, filter_mode):
    """
    Filter celestial objects based on the current filter mode.

    Args:
        celestial_objects: List of all celestial objects
        filter_mode: Current filter type ("all" or specific object type)

    Returns:
        Filtered list of celestial objects
    """
    if filter_mode == "all":
        return celestial_objects[:]
    else:
        return [obj for obj in celestial_objects if obj.type == filter_mode]

def announce_help(speech_queue):
    """
    Announce all available keyboard controls.

    Args:
        speech_queue: Queue for speech messages
    """
    help_text = [
        "Accessible Space Atlas Keyboard Controls:",
        "Arrow keys: Navigate between objects spatially.",
        "J: Enter jump mode for list navigation.",
        "In jump mode: Up and Down arrows to browse, Enter to select.",
        "M: Cycle through user modes: Educational, Exploration, Advanced.",
        "F: Filter objects by type: All, Stars, Planets, Moons, and more.",
        "S: Search for objects by name.",
        "B: Bookmark the currently selected object.",
        "Number keys 0 through 9: Recall bookmarked objects. 0 is slot 10.",
        "Shift plus number: Overwrite specific bookmark slot.",
        "L: Toggle follow mode to lock camera on selected object.",
        "O: Toggle audio positioning - hierarchical (orbital) vs true scale (absolute A U).",
        "C: Cluster focus mode - amplify sounds of moons and spacecraft orbiting selected planet.",
        "T: Change time scale for orbital motion.",
        "P: Pause or resume dynamic object positions.",
        "U: Cycle distance units: A U, kilometers, miles.",
        "V: Announce current object's velocity and speed.",
        "R: Announce distance from current object to reference object (default Earth).",
        "Shift plus R: Set current object as the reference for distance measurements.",
        "Page Up: Zoom in on visualization.",
        "Page Down: Zoom out on visualization.",
        "Home: Reset zoom to default.",
        "E: Export all celestial objects to CSV file.",
        "Minus key: Decrease master volume by 10 percent.",
        "Equals key: Increase master volume by 10 percent.",
        "W: Check space weather conditions manually.",
        "Note: Space weather is automatically monitored every 60 seconds with audio alerts.",
        "H: Hear this help message.",
        "End of help."
    ]
    for line in help_text:
        speech_queue.put(line)

def search_objects_by_name(celestial_objects, query):
    """
    Search for celestial objects by name (case-insensitive partial match).

    Args:
        celestial_objects: List of all celestial objects
        query: Search query string

    Returns:
        List of matching celestial objects
    """
    if not query:
        return []

    query_lower = query.lower()
    matches = [obj for obj in celestial_objects if query_lower in obj.name.lower()]
    return matches


def export_to_csv(celestial_objects, config_manager, filename="celestial_objects_export.csv"):
    """
    Export celestial objects to CSV file.

    Args:
        celestial_objects: List of all celestial objects
        config_manager: ConfigManager instance for distance formatting
        filename: Output filename (default: celestial_objects_export.csv)

    Returns:
        Full path to exported file, or None if export failed
    """
    try:
        # Get absolute path in current directory
        filepath = os.path.abspath(filename)

        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            writer.writerow([
                'Name', 'Type', 'Parent',
                'X (AU)', 'Y (AU)', 'Z (AU)',
                'Distance from Sun (AU)',
                'VX (AU/day)', 'VY (AU/day)', 'VZ (AU/day)',
                'Speed (km/s)'
            ])

            # Write object data
            for obj in celestial_objects:
                # Calculate speed in km/s
                speed_au_day = (obj.vx**2 + obj.vy**2 + obj.vz**2) ** 0.5
                speed_km_s = speed_au_day * config_manager.AU_PER_DAY_TO_KM_PER_SEC

                writer.writerow([
                    obj.name,
                    obj.type,
                    obj.parent or 'Sun',
                    f"{obj.x:.6f}",
                    f"{obj.y:.6f}",
                    f"{obj.z:.6f}",
                    f"{obj.distance:.6f}",
                    f"{obj.vx:.9f}",
                    f"{obj.vy:.9f}",
                    f"{obj.vz:.9f}",
                    f"{speed_km_s:.4f}"
                ])

        logging.info(f"Exported {len(celestial_objects)} objects to {filepath}")
        return filepath

    except Exception as e:
        logging.error(f"Failed to export to CSV: {e}")
        return None

def apply_cluster_focus_volumes(celestial_objects, cluster_focus_mode, focused_parent, master_vol=1.0):
    """
    Apply volume adjustments based on cluster focus mode and master volume.

    Args:
        celestial_objects: List of all celestial objects
        cluster_focus_mode: Whether cluster focus is active
        focused_parent: The parent object being focused on (or None)
        master_vol: Master volume multiplier (0.0 to 1.0)
    """
    if not cluster_focus_mode or not focused_parent:
        # Reset all volumes to normal (with master volume applied)
        for obj in celestial_objects:
            if obj.sound:
                obj.sound.set_volume(1.0 * master_vol)
        return

    # Apply cluster focus volume adjustments (with master volume applied)
    for obj in celestial_objects:
        if obj.sound:
            if obj.parent == focused_parent.name:
                # Child objects: amplify
                obj.sound.set_volume(1.0 * master_vol)
            elif obj.name == focused_parent.name:
                # The parent itself: normal
                obj.sound.set_volume(0.8 * master_vol)
            else:
                # All other objects: reduce
                obj.sound.set_volume(0.15 * master_vol)

def get_audio_position(obj, objects_by_name, hierarchical_mode):
    """
    Calculate audio position based on positioning mode.

    Args:
        obj: Celestial object
        objects_by_name: Dictionary mapping object names to objects
        hierarchical_mode: True for orbital hierarchy, False for true scale

    Returns:
        Tuple of (x, y, z, distance) for audio positioning
    """
    if hierarchical_mode and obj.parent and obj.parent in objects_by_name:
        # Hierarchical mode: position relative to parent
        parent_obj = objects_by_name[obj.parent]
        audio_x = obj.x - parent_obj.x
        audio_y = obj.y - parent_obj.y
        audio_z = obj.z - parent_obj.z
        audio_distance = (audio_x**2 + audio_y**2 + audio_z**2) ** 0.5
        logging.debug(f"{obj.name}: HIERARCHICAL relative to {obj.parent}, distance={audio_distance:.3f} AU")
    else:
        # True scale mode: use absolute heliocentric position
        audio_x = obj.x
        audio_y = obj.y
        audio_z = obj.z
        audio_distance = obj.distance
        mode_reason = "TRUE SCALE" if not hierarchical_mode else f"NO PARENT (parent={obj.parent})"
        logging.debug(f"{obj.name}: {mode_reason}, distance={audio_distance:.3f} AU")

    return audio_x, audio_y, audio_z, audio_distance

# SpeechHandler class is now imported from ui.speech_handler

# Function to fetch celestial objects data from Horizons API
def fetch_celestial_objects():
    """
    Fetch data for all known celestial objects using the API client.
    """
    api_client = HorizonsAPIClient()
    celestial_database = CelestialDatabase()
    objects_to_fetch = celestial_database.get_all_objects()
    return api_client.fetch_celestial_objects(objects_to_fetch)

# get_all_celestial_objects is now in CelestialDatabase.get_all_objects()
# get_next_object is now NavigationController.get_next_spatial_object()

# Function to fetch celestial objects data periodically
def data_fetch_thread(celestial_objects, lock, speech_queue):
    while True:
        fetched_objects = fetch_celestial_objects()
        with lock:
            celestial_objects.clear()
            celestial_objects.extend(fetched_objects)
        # Announce update
        speech_queue.put("Celestial data updated.")
        time.sleep(3600)  # Update every hour

# Main Function
def main():
    global selection_mode, selection_index, filter_mode, search_mode, search_query, follow_mode, followed_object, cluster_focus_mode, focused_parent, hierarchical_audio_mode, master_volume, reference_object_name
    global help_mode, help_navigator, tree_mode, tree_navigator

    # Initialize configuration manager
    config_manager = ConfigManager()

    # Initialize master volume from saved preferences
    master_volume = config_manager.master_volume

    # Initialize audio engine
    audio_engine = AudioEngine()
    logging.info("AudioEngine initialized for 3D spatial audio")

    # Initialize ambient audio manager (will be set up after speech_queue is created)
    ambient_manager = None

    # Initialize speech handler
    speech_queue = queue.Queue()
    stop_event = threading.Event()
    speech_handler = SpeechHandler(speech_queue, stop_event)
    speech_handler.start()

    # Initialize Cytolk for screen-reader support
    if cytolk_available and tolk:
        try:
            tolk.load()  # Initialize Cytolk
            speech_queue.put("Initializing Accessible Space Atlas. Screen reader loaded.")
        except Exception as e:
            logging.error(f"Error initializing screen reader: {e}")
            sys.exit(1)
    else:
        logging.warning("Cytolk is not available. Screen reader support is disabled.")

    # Initialize ambient audio manager
    ambient_manager = AmbientAudioManager(speech_queue, config_manager)

    # Initialize celestial objects list
    celestial_objects = []
    filtered_objects = []  # Filtered subset based on filter_mode

    # Initialize threading lock
    lock = threading.Lock()

    # Loading state for UI feedback
    loading_state = {'status': 'starting', 'progress': 0, 'message': 'Initializing...'}
    loading_lock = threading.Lock()

    def update_loading_state(status, progress, message):
        """Update loading state thread-safely."""
        with loading_lock:
            loading_state['status'] = status
            loading_state['progress'] = progress
            loading_state['message'] = message

    # Fetch data in background thread to avoid blocking UI
    def initial_data_fetch():
        """Background thread to fetch initial celestial data."""
        logging.info("Starting background data fetch...")
        update_loading_state('loading', 10, 'Checking cache...')
        speech_queue.put("Loading celestial objects. Please wait.")

        # Try to load from cache first for fast startup
        api_client = HorizonsAPIClient()
        cached_objects = api_client._load_from_cache()

        if cached_objects:
            update_loading_state('cache', 30, f'Loaded {len(cached_objects)} objects from cache')
            speech_queue.put(f"Quick load: {len(cached_objects)} objects from cache. Fetching updates...")

            # Use cached data immediately
            with lock:
                celestial_objects.clear()
                celestial_objects.extend(cached_objects)
                filtered_objects.clear()
                filtered_objects.extend(celestial_objects)

            logging.info(f"Loaded {len(cached_objects)} objects from cache")

        # Now fetch fresh data from API
        update_loading_state('fetching', 50, 'Fetching from NASA API...')
        fetched_objects = fetch_celestial_objects()

        if fetched_objects:
            with lock:
                celestial_objects.clear()
                celestial_objects.extend(fetched_objects)
                filtered_objects.clear()
                filtered_objects.extend(celestial_objects)

            logging.info(f"Fetched {len(fetched_objects)} celestial objects from API.")
            update_loading_state('audio', 70, 'Generating spatial audio...')
        elif not cached_objects:
            # No API data and no cache
            update_loading_state('error', 0, 'Failed to load celestial objects')
            speech_queue.put("Error: Could not load celestial objects. Check internet connection.")
            return

        # Generate 3D spatial audio for all objects using relative positions
        audio_params = config_manager.get_audio_params()
        logging.info(f"Generating spatial audio with complexity: {audio_params['complexity']}")

        with lock:
            # Build object lookup by name for parent-child relationships
            objects_by_name = {obj.name: obj for obj in celestial_objects}
            total_objects = len(celestial_objects)

            for i, obj in enumerate(celestial_objects):
                # Get audio position based on current mode
                audio_x, audio_y, audio_z, audio_distance = get_audio_position(
                    obj, objects_by_name, hierarchical_audio_mode
                )

                spatial_sound = audio_engine.create_spatial_sound(
                    obj.type, audio_x, audio_y, audio_z, audio_distance, audio_params
                )
                obj.set_sound(spatial_sound)

                # Update progress
                if i % 10 == 0:
                    progress = 70 + int((i / total_objects) * 25)
                    update_loading_state('audio', progress, f'Generating audio... ({i+1}/{total_objects})')

        logging.info("3D spatial audio generation complete")

        # Log cache stats
        cache_stats = audio_engine.get_cache_stats()
        logging.info(f"Audio cache stats: {cache_stats}")

        update_loading_state('weather', 95, 'Checking space weather...')

        data_source = "API" if fetched_objects else "cache"
        obj_count = len(fetched_objects) if fetched_objects else len(cached_objects)
        speech_queue.put(f"Loaded {obj_count} celestial objects from {data_source}. Ready to explore. Press H for help.")

        # Check for space weather warnings
        logging.info("Checking space weather conditions...")
        space_weather = SpaceWeatherClient()
        warnings = space_weather.get_active_warnings()

        if warnings:
            speech_queue.put(f"Space weather alert: {len(warnings)} active events.")
            for warning in warnings:
                speech_queue.put(warning)
                logging.info(f"Space weather: {warning}")
        else:
            logging.info("No significant space weather events detected")

        update_loading_state('complete', 100, 'Ready')

    # Start initial data fetch in background
    initial_fetch_thread = threading.Thread(target=initial_data_fetch, daemon=True)
    initial_fetch_thread.start()

    # Start periodic data fetching in a separate thread
    data_thread = threading.Thread(target=data_fetch_thread, args=(celestial_objects, lock, speech_queue), daemon=True)
    data_thread.start()

    # Initialize navigation controller
    nav_controller = NavigationController()

    # Initialize Pygame clock
    clock = pygame.time.Clock()
    selected_object = None

    # Select the first object when data is loaded
    selected_object = None
    first_selection_made = False

    # Space weather monitoring
    space_weather_warnings = []  # Store current warnings
    space_weather_lock = threading.Lock()  # Protect warnings list
    last_weather_check = time.time()  # Track last check time
    WEATHER_CHECK_INTERVAL = 60  # Check every 60 seconds

    # Main loop
    running = True
    try:
        while running:
            # Auto-select first object once data is loaded
            if not first_selection_made and len(filtered_objects) > 0:
                with lock:
                    if len(filtered_objects) > 0:
                        selected_object = 0
                        obj = filtered_objects[selected_object]
                        obj.announce(speech_queue, config_manager)
                        obj.play_sound(master_volume)
                        first_selection_made = True

            # Periodic space weather check (every 60 seconds)
            current_time = time.time()
            if current_time - last_weather_check >= WEATHER_CHECK_INTERVAL:
                last_weather_check = current_time

                def poll_space_weather():
                    """Background thread to check space weather."""
                    space_weather = SpaceWeatherClient()
                    warnings = space_weather.get_active_warnings()

                    with space_weather_lock:
                        # Check if there are new warnings
                        new_warnings = [w for w in warnings if w not in space_weather_warnings]
                        space_weather_warnings.clear()
                        space_weather_warnings.extend(warnings)

                    # Announce and play tones for new warnings
                    if new_warnings:
                        logging.info(f"Space weather update: {len(new_warnings)} new events detected")
                        speech_queue.put(f"Space weather alert: {len(new_warnings)} new events detected.")

                        for warning in new_warnings:
                            # Determine warning type and play appropriate tone
                            warning_lower = warning.lower()
                            if 'flare' in warning_lower:
                                tone = audio_engine.create_warning_tone('flare', duration=1.5)
                                tone.play()
                            elif 'cme' in warning_lower or 'coronal mass ejection' in warning_lower:
                                tone = audio_engine.create_warning_tone('cme', duration=1.5)
                                tone.play()
                            elif 'storm' in warning_lower or 'geomagnetic' in warning_lower:
                                tone = audio_engine.create_warning_tone('storm', duration=1.5)
                                tone.play()

                            # Announce the warning
                            speech_queue.put(warning)
                            logging.info(f"Space weather: {warning}")

                            # Small delay between warnings to prevent audio overlap
                            time.sleep(0.5)
                    else:
                        logging.info("Space weather check: No new events")

                # Run in background to avoid blocking
                weather_poll_thread = threading.Thread(target=poll_space_weather, daemon=True)
                weather_poll_thread.start()

            for event in pygame.event.get():
                # Debug: Log all events to help diagnose Control key issue
                if event.type not in (MOUSEMOTION,):  # Skip noisy mouse events
                    logging.debug(f"Event received: type={event.type}, event={event}")

                if event.type == QUIT:
                    logging.info("QUIT event received - closing application")
                    speech_queue.put("Exiting Accessible Space Atlas.")
                    running = False

                elif event.type == KEYDOWN:
                    # Log key presses for debugging
                    logging.info(f"KEYDOWN: key={event.key}, mod={event.mod}, unicode='{event.unicode}'")

                    # Help mode takes highest priority
                    if help_mode:
                        if event.key == K_UP:
                            help_navigator.move_up()
                        elif event.key == K_DOWN:
                            help_navigator.move_down()
                        elif event.key == K_RETURN or event.key == K_KP_ENTER:
                            help_navigator.read_current()
                        elif event.key == K_ESCAPE:
                            help_mode = False
                            help_navigator = None
                            speech_queue.put("Exiting help.")
                        # All other keys ignored in help mode

                    # Tree navigation mode
                    elif tree_mode:
                        if event.key == K_UP:
                            tree_navigator.move_up()
                        elif event.key == K_DOWN:
                            tree_navigator.move_down()
                        elif event.key == K_RIGHT or event.key == K_RETURN or event.key == K_KP_ENTER:
                            result = tree_navigator.enter()
                            if result is not None:
                                # Selected a leaf object - exit tree mode and jump to it
                                with lock:
                                    try:
                                        selected_object = filtered_objects.index(result)
                                        result.announce(speech_queue, config_manager)
                                        result.play_sound(master_volume)
                                        # Switch ambient audio if enabled
                                        if ambient_manager.is_enabled:
                                            ambient_manager.play_for_object(result)
                                        tree_mode = False
                                        tree_navigator = None
                                        speech_queue.put(f"Jumped to {result.name}.")
                                    except ValueError:
                                        speech_queue.put(f"{result.name} is currently filtered out. Change filter to see it.")
                        elif event.key == K_LEFT:
                            if not tree_navigator.go_back():
                                # At root, just announce - don't exit
                                speech_queue.put("At top level. Press Escape to exit.")
                        elif event.key == K_TAB:
                            mods = pygame.key.get_mods()
                            if mods & KMOD_SHIFT:
                                tree_navigator.unflatten()
                            else:
                                tree_navigator.flatten()
                        elif event.key == K_ESCAPE:
                            tree_mode = False
                            tree_navigator = None
                            speech_queue.put("Tree navigation cancelled.")

                    elif not selection_mode and not search_mode:
                        # Normal navigation keys
                        direction = None
                        if event.key == K_LEFT:
                            direction = 'left'
                        elif event.key == K_RIGHT:
                            direction = 'right'
                        elif event.key == K_UP:
                            direction = 'up'
                        elif event.key == K_DOWN:
                            direction = 'down'
                        elif event.key == K_j:
                            # Activate tree navigation mode
                            tree_mode = True
                            tree_navigator = TreeNavigator(speech_queue, config_manager)
                            with lock:
                                tree_navigator.build_tree(celestial_objects)
                            tree_navigator.announce_entry()
                        elif event.key == K_m:
                            # Toggle user mode
                            config_manager.cycle_mode()
                            speech_queue.put(config_manager.get_mode_change_announcement())

                            # Regenerate audio with new complexity settings using relative positions
                            audio_params = config_manager.get_audio_params()
                            logging.info(f"Regenerating audio for {audio_params['complexity']} mode")
                            with lock:
                                # Build object lookup for parent-child relationships
                                objects_by_name = {obj.name: obj for obj in celestial_objects}

                                for obj in celestial_objects:
                                    # Get audio position based on current mode
                                    audio_x, audio_y, audio_z, audio_distance = get_audio_position(
                                        obj, objects_by_name, hierarchical_audio_mode
                                    )

                                    spatial_sound = audio_engine.create_spatial_sound(
                                        obj.type, audio_x, audio_y, audio_z, audio_distance, audio_params
                                    )
                                    obj.set_sound(spatial_sound)
                        elif event.key == K_t:
                            # Cycle time scale
                            new_time_scale = config_manager.cycle_time_scale()
                            description = config_manager.get_time_scale_description()
                            speech_queue.put(f"Time scale: {description}")
                        elif event.key == K_p:
                            # Toggle dynamic positions
                            is_dynamic = config_manager.toggle_dynamic_positions()
                            status = "enabled" if is_dynamic else "paused"
                            speech_queue.put(f"Dynamic positions {status}")
                        elif event.key == K_w:
                            # Check space weather
                            speech_queue.put("Checking space weather conditions...")

                            def check_weather():
                                space_weather = SpaceWeatherClient()
                                warnings = space_weather.get_active_warnings()

                                if warnings:
                                    speech_queue.put(f"Space weather alert: {len(warnings)} active events.")
                                    for warning in warnings:
                                        speech_queue.put(warning)
                                else:
                                    speech_queue.put("No significant space weather events detected. Conditions are calm.")

                            weather_thread = threading.Thread(target=check_weather, daemon=True)
                            weather_thread.start()
                        elif event.key == K_f:
                            # Cycle object filter
                            current_index = filter_types.index(filter_mode)
                            next_index = (current_index + 1) % len(filter_types)
                            filter_mode = filter_types[next_index]

                            # Apply filter
                            with lock:
                                filtered_objects.clear()
                                filtered_objects.extend(filter_objects(celestial_objects, filter_mode))

                            # Announce filter change
                            if filter_mode == "all":
                                speech_queue.put(f"Filter: All objects. {len(filtered_objects)} objects visible.")
                            else:
                                speech_queue.put(f"Filter: {filter_mode}s only. {len(filtered_objects)} objects visible.")

                            # Reset selection to first filtered object
                            if len(filtered_objects) > 0:
                                selected_object = 0
                                obj = filtered_objects[selected_object]
                                obj.announce(speech_queue, config_manager)
                                obj.play_sound(master_volume)
                            else:
                                selected_object = None
                                speech_queue.put(f"No {filter_mode}s found.")
                        elif event.key == K_h:
                            # Enter help navigation mode
                            mods = pygame.key.get_mods()
                            help_mode = True
                            if mods & KMOD_SHIFT:
                                # Shift+H: Educational content about space
                                help_navigator = EducationalHelp(speech_queue, config_manager)
                            else:
                                # H: Keystroke help
                                help_navigator = KeystrokeHelp(speech_queue, config_manager)
                            help_navigator.announce_entry()
                        elif event.key == K_s:
                            # Enter search mode
                            search_mode = True
                            search_query = ""
                            speech_queue.put("Search mode activated. Type object name and press Enter. Press Escape to cancel.")
                        elif event.key == K_b:
                            # Bookmark current object
                            if selected_object is not None and len(filtered_objects) > 0:
                                current_obj = filtered_objects[selected_object]
                                # Check if Shift is held for manual slot selection
                                mods = pygame.key.get_mods()
                                if mods & KMOD_SHIFT:
                                    # Shift+B: Announce current bookmarks
                                    if config_manager.bookmarks:
                                        speech_queue.put(f"Current bookmarks: {len(config_manager.bookmarks)} saved.")
                                        for slot, name in sorted(config_manager.bookmarks.items()):
                                            slot_display = slot if slot != 0 else 10
                                            speech_queue.put(f"Slot {slot_display}: {name}")
                                    else:
                                        speech_queue.put("No bookmarks saved. Press B to bookmark current object.")
                                else:
                                    # Find next available bookmark slot
                                    slot = config_manager.get_next_available_slot()
                                    if slot is not None:
                                        config_manager.add_bookmark(slot, current_obj.name)
                                        slot_display = slot if slot != 0 else 10
                                        speech_queue.put(f"Bookmarked {current_obj.name} as bookmark {slot_display}. Press {slot} to recall.")
                                    else:
                                        # All slots full
                                        speech_queue.put("All 10 bookmark slots are full. Hold Shift and press a number key to overwrite a specific slot.")
                            else:
                                speech_queue.put("No object selected to bookmark.")
                        elif event.key in [K_0, K_1, K_2, K_3, K_4, K_5, K_6, K_7, K_8, K_9]:
                            # Bookmark recall or overwrite
                            bookmark_num = event.key - K_0  # Convert key to number (0-9)
                            mods = pygame.key.get_mods()

                            if mods & KMOD_SHIFT:
                                # Shift+Number: Overwrite bookmark slot
                                if selected_object is not None and len(filtered_objects) > 0:
                                    current_obj = filtered_objects[selected_object]
                                    config_manager.add_bookmark(bookmark_num, current_obj.name)
                                    slot_display = bookmark_num if bookmark_num != 0 else 10
                                    speech_queue.put(f"Saved {current_obj.name} to bookmark slot {slot_display}.")
                                else:
                                    speech_queue.put("No object selected to bookmark.")
                            else:
                                # Regular: Recall bookmark
                                bookmark_name = config_manager.get_bookmark(bookmark_num)
                                if bookmark_name:
                                    # Find object by name in celestial_objects
                                    bookmark_obj = None
                                    with lock:
                                        for obj in celestial_objects:
                                            if obj.name == bookmark_name:
                                                bookmark_obj = obj
                                                break

                                    if bookmark_obj:
                                        # Find object in filtered_objects
                                        try:
                                            selected_object = filtered_objects.index(bookmark_obj)
                                            bookmark_obj.announce(speech_queue, config_manager)
                                            bookmark_obj.play_sound(master_volume)
                                            # Switch ambient audio if enabled
                                            if ambient_manager.is_enabled:
                                                ambient_manager.play_for_object(bookmark_obj)
                                            slot_display = bookmark_num if bookmark_num != 0 else 10
                                            speech_queue.put(f"Recalled bookmark {slot_display}: {bookmark_obj.name}.")
                                        except ValueError:
                                            speech_queue.put(f"Bookmark ({bookmark_name}) is filtered out. Change filter to see it.")
                                    else:
                                        speech_queue.put(f"Bookmarked object '{bookmark_name}' not found in current data.")
                                else:
                                    slot_display = bookmark_num if bookmark_num != 0 else 10
                                    speech_queue.put(f"No bookmark in slot {slot_display}. Press B to bookmark, or Shift+{bookmark_num} to save to this slot.")
                        elif event.key == K_l:
                            # Toggle follow mode
                            if selected_object is not None and len(filtered_objects) > 0:
                                follow_mode = not follow_mode
                                if follow_mode:
                                    followed_object = filtered_objects[selected_object]
                                    speech_queue.put(f"Follow mode activated. Camera locked on {followed_object.name}.")
                                else:
                                    followed_object = None
                                    speech_queue.put("Follow mode deactivated. Camera unlocked.")
                            else:
                                speech_queue.put("No object selected. Select an object first to enable follow mode.")
                        elif event.key == K_o:
                            # Toggle audio positioning mode (hierarchical vs true scale)
                            hierarchical_audio_mode = not hierarchical_audio_mode

                            mode_name = "Hierarchical" if hierarchical_audio_mode else "True Scale"
                            mode_desc = "orbital relationships" if hierarchical_audio_mode else "absolute solar system distances"
                            speech_queue.put(f"Audio positioning: {mode_name} mode. Using {mode_desc}.")
                            logging.info(f"Switched to {mode_name} audio positioning mode (hierarchical_audio_mode={hierarchical_audio_mode})")

                            # Regenerate audio with new positioning
                            audio_params = config_manager.get_audio_params()
                            regenerated_count = 0
                            with lock:
                                objects_by_name = {obj.name: obj for obj in celestial_objects}

                                for obj in celestial_objects:
                                    audio_x, audio_y, audio_z, audio_distance = get_audio_position(
                                        obj, objects_by_name, hierarchical_audio_mode
                                    )
                                    spatial_sound = audio_engine.create_spatial_sound(
                                        obj.type, audio_x, audio_y, audio_z, audio_distance, audio_params
                                    )
                                    obj.set_sound(spatial_sound)
                                    regenerated_count += 1

                            logging.info(f"Regenerated audio for {regenerated_count} objects in {mode_name} mode")
                        elif event.key == K_MINUS:
                            # Decrease master volume
                            master_volume = max(0.0, master_volume - 0.1)
                            config_manager.set_master_volume(master_volume)  # Persist
                            volume_percent = int(master_volume * 100)
                            speech_queue.put(f"Master volume: {volume_percent} percent")
                            logging.info(f"Master volume decreased to {volume_percent}%")

                            # Apply new volume to all sounds
                            with lock:
                                apply_cluster_focus_volumes(celestial_objects, cluster_focus_mode, focused_parent, master_volume)
                        elif event.key == K_EQUALS:
                            # Increase master volume
                            master_volume = min(1.0, master_volume + 0.1)
                            config_manager.set_master_volume(master_volume)  # Persist
                            volume_percent = int(master_volume * 100)
                            speech_queue.put(f"Master volume: {volume_percent} percent")
                            logging.info(f"Master volume increased to {volume_percent}%")

                            # Apply new volume to all sounds
                            with lock:
                                apply_cluster_focus_volumes(celestial_objects, cluster_focus_mode, focused_parent, master_volume)
                        elif event.key == K_c:
                            # Toggle cluster focus mode
                            if selected_object is not None and len(filtered_objects) > 0:
                                current_obj = filtered_objects[selected_object]

                                # Check if this object has children (moons, spacecraft, etc.)
                                with lock:
                                    children = [obj for obj in celestial_objects if obj.parent == current_obj.name]

                                if children:
                                    cluster_focus_mode = not cluster_focus_mode
                                    if cluster_focus_mode:
                                        focused_parent = current_obj
                                        speech_queue.put(f"Cluster focus activated on {current_obj.name}. {len(children)} orbiting objects amplified.")
                                        logging.info(f"Cluster focus: {current_obj.name} has {len(children)} children")
                                    else:
                                        focused_parent = None
                                        speech_queue.put("Cluster focus deactivated. All objects at normal volume.")

                                    # Apply volume changes
                                    with lock:
                                        apply_cluster_focus_volumes(celestial_objects, cluster_focus_mode, focused_parent, master_volume)
                                else:
                                    speech_queue.put(f"{current_obj.name} has no orbiting objects. Select a planet with moons or spacecraft.")
                            else:
                                speech_queue.put("No object selected. Select an object first to enable cluster focus.")
                        elif event.key == K_u:
                            # Cycle distance units
                            config_manager.cycle_distance_unit()
                            unit_name = config_manager.get_distance_unit_name()
                            speech_queue.put(f"Distance unit changed to {unit_name}.")
                            logging.info(f"Distance unit changed to {unit_name}")

                            # Re-announce current object with new units
                            if selected_object is not None and len(filtered_objects) > 0:
                                obj = filtered_objects[selected_object]
                                obj.announce(speech_queue, config_manager)
                        elif event.key == K_v:
                            # Announce velocity of current object
                            if selected_object is not None and len(filtered_objects) > 0:
                                obj = filtered_objects[selected_object]
                                velocity_announcement = config_manager.get_velocity_announcement(obj)
                                speech_queue.put(velocity_announcement)
                            else:
                                speech_queue.put("No object selected. Select an object to hear its velocity.")
                        elif event.key == K_r:
                            # R: Announce relative distance / Shift+R: Set reference object
                            mods = pygame.key.get_mods()

                            if mods & KMOD_SHIFT:
                                # Shift+R: Set current object as reference
                                if selected_object is not None and len(filtered_objects) > 0:
                                    obj = filtered_objects[selected_object]
                                    reference_object_name = obj.name
                                    speech_queue.put(f"Reference object set to {reference_object_name}. Press R to measure distances from here.")
                                else:
                                    speech_queue.put("No object selected to set as reference.")
                            else:
                                # R: Announce distance from current to reference
                                if selected_object is not None and len(filtered_objects) > 0:
                                    current_obj = filtered_objects[selected_object]

                                    # Find reference object
                                    reference_obj = None
                                    with lock:
                                        for obj in celestial_objects:
                                            if obj.name == reference_object_name:
                                                reference_obj = obj
                                                break

                                    if reference_obj:
                                        if current_obj.name == reference_obj.name:
                                            speech_queue.put(f"{current_obj.name} is the reference object. Press Shift+R on another object to change reference.")
                                        else:
                                            relative_announcement = config_manager.get_relative_distance_announcement(current_obj, reference_obj)
                                            speech_queue.put(relative_announcement)
                                    else:
                                        speech_queue.put(f"Reference object '{reference_object_name}' not found. Press Shift+R to set a new reference.")
                                else:
                                    speech_queue.put("No object selected.")
                        elif event.key == K_e:
                            # Export to CSV
                            with lock:
                                filepath = export_to_csv(celestial_objects, config_manager)

                            if filepath:
                                speech_queue.put(f"Exported {len(celestial_objects)} objects to CSV file.")
                                speech_queue.put(f"File saved as: {os.path.basename(filepath)}")
                            else:
                                speech_queue.put("Failed to export to CSV. Check console for errors.")
                        elif event.key == K_PAGEUP:
                            # Zoom in
                            new_zoom = config_manager.zoom_in()
                            speech_queue.put(config_manager.get_zoom_description())
                            logging.info(f"Zoom in: {new_zoom}")
                        elif event.key == K_PAGEDOWN:
                            # Zoom out
                            new_zoom = config_manager.zoom_out()
                            speech_queue.put(config_manager.get_zoom_description())
                            logging.info(f"Zoom out: {new_zoom}")
                        elif event.key == K_HOME:
                            # Reset zoom
                            config_manager.reset_zoom()
                            speech_queue.put("Zoom reset to 100 percent.")
                            logging.info("Zoom reset to 100%")
                        elif event.key == K_a:
                            # Toggle ambient audio
                            if selected_object is not None and len(filtered_objects) > 0:
                                current_obj = filtered_objects[selected_object]
                                ambient_manager.toggle(current_obj)
                            else:
                                ambient_manager.toggle(None)

                        if direction and not selection_mode and not search_mode and not help_mode and not tree_mode:
                            with lock:
                                if filtered_objects and selected_object is not None:
                                    next_index = nav_controller.get_next_spatial_object(filtered_objects, selected_object, direction)
                                    if next_index != selected_object and next_index is not None:
                                        selected_object = next_index
                                        obj = filtered_objects[selected_object]
                                        obj.announce(speech_queue, config_manager)
                                        obj.play_sound(master_volume)
                                        # Switch ambient audio if enabled
                                        if ambient_manager.is_enabled:
                                            ambient_manager.play_for_object(obj)
                    elif selection_mode:
                        # Selection mode navigation
                        if event.key == K_UP:
                            if selection_index > 0:
                                selection_index -= 1
                                announce_current_selection(filtered_objects, selection_index, speech_queue, config_manager)
                        elif event.key == K_DOWN:
                            if selection_index < len(filtered_objects) - 1:
                                selection_index += 1
                                announce_current_selection(filtered_objects, selection_index, speech_queue, config_manager)
                        elif event.key == K_RETURN or event.key == K_KP_ENTER:
                            # Confirm selection
                            with lock:
                                selected_object = selection_index
                                obj = filtered_objects[selected_object]
                                obj.announce(speech_queue, config_manager)
                                obj.play_sound(master_volume)
                                # Switch ambient audio if enabled
                                if ambient_manager.is_enabled:
                                    ambient_manager.play_for_object(obj)
                            # Exit selection mode
                            selection_mode = False
                            speech_queue.put(f"Jumped to {obj.name}.")
                    elif search_mode:
                        # Search mode input handling
                        if event.key == K_ESCAPE:
                            # Cancel search
                            search_mode = False
                            search_query = ""
                            speech_queue.put("Search cancelled.")
                        elif event.key == K_RETURN or event.key == K_KP_ENTER:
                            # Execute search
                            with lock:
                                matches = search_objects_by_name(celestial_objects, search_query)

                            if len(matches) == 0:
                                speech_queue.put(f"No objects found matching '{search_query}'.")
                            elif len(matches) == 1:
                                # Single match - select it directly
                                match_obj = matches[0]
                                # Find index in filtered_objects
                                try:
                                    selected_object = filtered_objects.index(match_obj)
                                    match_obj.announce(speech_queue, config_manager)
                                    match_obj.play_sound(master_volume)
                                    # Switch ambient audio if enabled
                                    if ambient_manager.is_enabled:
                                        ambient_manager.play_for_object(match_obj)
                                    speech_queue.put(f"Found and selected: {match_obj.name}.")
                                except ValueError:
                                    speech_queue.put(f"Found {match_obj.name}, but it's filtered out. Change filter to see it.")
                            else:
                                # Multiple matches - announce them
                                speech_queue.put(f"Found {len(matches)} matches for '{search_query}':")
                                for match in matches[:5]:  # Limit to first 5
                                    speech_queue.put(f"{match.name}, {match.type}")
                                if len(matches) > 5:
                                    speech_queue.put(f"And {len(matches) - 5} more. Refine your search.")

                            # Exit search mode
                            search_mode = False
                            search_query = ""
                        elif event.key == K_BACKSPACE:
                            # Delete last character
                            if len(search_query) > 0:
                                search_query = search_query[:-1]
                                if search_query:
                                    speech_queue.put(search_query[-1] if search_query else "empty")
                                else:
                                    speech_queue.put("Query cleared.")
                        elif event.unicode and event.unicode.isprintable():
                            # Add typed character to query
                            search_query += event.unicode
                            speech_queue.put(event.unicode)

            # Update positions of celestial objects if dynamic mode is enabled
            if config_manager.dynamic_positions:
                with lock:
                    for obj in celestial_objects:
                        obj.update_position(config_manager.time_scale)

            # Render
            SCREEN.fill(BLACK)

            # Calculate camera offset for follow mode
            camera_offset = (0, 0)
            if follow_mode and followed_object is not None:
                # Offset to center the followed object on screen
                center_x = WIDTH // 2
                center_y = HEIGHT // 2
                followed_screen_pos = followed_object.screen_pos
                camera_offset = (center_x - followed_screen_pos[0], center_y - followed_screen_pos[1])

            # Display mode indicator and time scale in top-right corner
            mode_text = config_manager.get_mode_indicator_text()
            mode_surface = FONT.render(mode_text, True, WHITE)
            SCREEN.blit(mode_surface, (WIDTH - 250, 10))

            # Display time scale
            time_scale_text = f"Time: {config_manager.get_time_scale_description()}"
            time_surface = FONT.render(time_scale_text, True, WHITE)
            SCREEN.blit(time_surface, (WIDTH - 250, 30))

            # Display dynamic status
            dynamic_text = "Dynamic: " + ("ON" if config_manager.dynamic_positions else "PAUSED")
            dynamic_surface = FONT.render(dynamic_text, True, WHITE)
            SCREEN.blit(dynamic_surface, (WIDTH - 250, 50))

            # Display filter status
            if filter_mode == "all":
                filter_text = f"Filter: All ({len(filtered_objects)} objects)"
            else:
                filter_text = f"Filter: {filter_mode}s ({len(filtered_objects)} objects)"
            filter_surface = FONT.render(filter_text, True, WHITE)
            SCREEN.blit(filter_surface, (WIDTH - 250, 70))

            # Display zoom level
            zoom_text = f"Zoom: {config_manager.get_zoom_description()}"
            zoom_surface = FONT.render(zoom_text, True, WHITE)
            SCREEN.blit(zoom_surface, (WIDTH - 250, 90))

            # Display distance unit
            unit_text = f"Units: {config_manager.get_distance_unit_name()}"
            unit_surface = FONT.render(unit_text, True, WHITE)
            SCREEN.blit(unit_surface, (WIDTH - 250, 110))

            # Display follow mode status
            if follow_mode and followed_object:
                follow_text = f"Follow: {followed_object.name}"
                follow_surface = FONT.render(follow_text, True, (255, 255, 0))  # Yellow for visibility
                SCREEN.blit(follow_surface, (WIDTH - 250, 130))

            # Display space weather warnings (top-left corner)
            with space_weather_lock:
                if space_weather_warnings:
                    # Warning header with alert color
                    warning_header = f"SPACE WEATHER ALERT ({len(space_weather_warnings)})"
                    header_surface = FONT.render(warning_header, True, (255, 100, 100))  # Red for alerts
                    SCREEN.blit(header_surface, (10, 10))

                    # Display first 3 warnings
                    for i, warning in enumerate(space_weather_warnings[:3]):
                        # Truncate long warnings for display
                        display_text = warning[:50] + "..." if len(warning) > 50 else warning
                        warning_surface = FONT.render(display_text, True, (255, 200, 100))  # Orange
                        SCREEN.blit(warning_surface, (10, 30 + i * 20))

            # Display search query if in search mode
            if search_mode:
                search_text = f"Search: {search_query}_"
                search_surface = FONT.render(search_text, True, (255, 255, 0))  # Yellow for visibility
                SCREEN.blit(search_surface, (50, HEIGHT - 50))

            # Show loading message with progress if no objects yet
            if len(filtered_objects) == 0:
                with loading_lock:
                    status = loading_state['status']
                    progress = loading_state['progress']
                    message = loading_state['message']

                # Main loading text
                loading_text = FONT.render(message, True, WHITE)
                text_rect = loading_text.get_rect(center=(WIDTH // 2, HEIGHT // 2))
                SCREEN.blit(loading_text, text_rect)

                # Progress bar
                bar_width = 400
                bar_height = 20
                bar_x = (WIDTH - bar_width) // 2
                bar_y = HEIGHT // 2 + 40

                # Background bar
                pygame.draw.rect(SCREEN, (50, 50, 50), (bar_x, bar_y, bar_width, bar_height))
                # Progress fill
                fill_width = int(bar_width * progress / 100)
                progress_color = (100, 200, 100) if status != 'error' else (200, 100, 100)
                pygame.draw.rect(SCREEN, progress_color, (bar_x, bar_y, fill_width, bar_height))
                # Border
                pygame.draw.rect(SCREEN, WHITE, (bar_x, bar_y, bar_width, bar_height), 2)

                # Progress percentage
                percent_text = FONT.render(f"{progress}%", True, WHITE)
                percent_rect = percent_text.get_rect(center=(WIDTH // 2, bar_y + bar_height + 20))
                SCREEN.blit(percent_text, percent_rect)

            # Get zoom level for rendering
            zoom = config_manager.zoom_level
            center_x = WIDTH // 2
            center_y = HEIGHT // 2

            with lock:
                for idx, obj in enumerate(filtered_objects):
                    # Determine color based on type
                    if obj.type == "Star":
                        color = STAR_COLOR
                    elif obj.type == "Planet":
                        color = PLANET_COLOR
                    elif obj.type == "Dwarf Planet":
                        color = DWARF_PLANET_COLOR
                    elif obj.type == "Moon":
                        color = MOON_COLOR
                    elif obj.type == "Asteroid":
                        color = ASTEROID_COLOR
                    elif obj.type == "Comet":
                        color = COMET_COLOR
                    elif obj.type == "Spacecraft":
                        color = SPACECRAFT_COLOR
                    else:
                        color = WHITE  # Default color for unknown types

                    # Apply zoom by scaling position relative to center
                    zoomed_x = center_x + int((obj.screen_pos[0] - center_x) * zoom)
                    zoomed_y = center_y + int((obj.screen_pos[1] - center_y) * zoom)

                    # Apply camera offset for follow mode
                    render_pos = (zoomed_x + camera_offset[0], zoomed_y + camera_offset[1])

                    # Scale object size with zoom (but clamp to reasonable range)
                    render_size = max(2, int(obj.size * zoom))

                    # Draw the object
                    pygame.draw.circle(SCREEN, color, render_pos, render_size)

                    # Highlight selected object
                    if selected_object == idx:
                        pygame.draw.circle(SCREEN, WHITE, render_pos, render_size + 5, 2)
                        # Display object name visually (optional)
                        text_surface = FONT.render(obj.name, True, WHITE)
                        SCREEN.blit(text_surface, (render_pos[0] + 10, render_pos[1] - 10))

            # Render selection list if in selection mode
            if selection_mode:
                # Calculate position for the list (e.g., top-left corner)
                list_x, list_y = 50, 50
                list_spacing = 25  # Space between list items

                # Semi-transparent background for the list
                s = pygame.Surface((300, min(30 * len(filtered_objects), HEIGHT - 100)))  # Width 300, Height depends on number of objects
                s.set_alpha(200)  # Transparency
                s.fill((50, 50, 50))  # Dark gray background
                SCREEN.blit(s, (list_x - 10, list_y - 10))

                for idx, obj in enumerate(filtered_objects):
                    if idx == selection_index:
                        # Highlight the selected item
                        text_color = (255, 255, 0)  # Yellow
                    else:
                        text_color = WHITE
                    text_surface = FONT.render(f"{idx + 1}. {obj.name} ({obj.type})", True, text_color)
                    SCREEN.blit(text_surface, (list_x, list_y + idx * list_spacing))

            # Update the display
            pygame.display.flip()
            clock.tick(30)  # 30 FPS

        # Log when main loop exits normally
        logging.info("Main loop exited. running=%s", running)

    except KeyboardInterrupt:
        logging.info("Program interrupted by user (KeyboardInterrupt).")
        speech_queue.put("Program interrupted by user.")
    except Exception as e:
        logging.error(f"Unexpected exception in main loop: {e}", exc_info=True)
    finally:
        logging.info("Entering finally block - shutting down")
        # Gracefully shut down ambient audio
        if ambient_manager:
            ambient_manager.shutdown()
        # Gracefully shut down speech handler
        speech_handler.shutdown()
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    main()
