# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SpaceAtless** is an accessible audio space exploration application that uses 3D spatial audio to represent celestial objects. Built with Pygame and designed for screen reader users, it provides an audio-based interface to explore the solar system using data from NASA's JPL Horizons API.

### Key Features
- **3D Spatial Audio**: Objects positioned in stereo space with distance-based effects
- **Screen Reader Integration**: Full Cytolk/Tolk support for accessibility
- **Three User Modes**: Educational (verbose), Exploration (balanced), Advanced (concise)
- **Real-time Data**: Fetches celestial object positions from NASA Horizons API
- **Multiple Object Categories**: Planets, dwarf planets, moons, asteroids, comets, and spacecraft

## Development Environment

### Conda Environment Setup

This project uses conda for dependency management. The conda environment should be set up with Python 3.11.

**Key packages required:**
- pygame (graphics and audio)
- numpy (audio processing)
- scipy (signal processing for audio filters)
- requests (API calls)
- cytolk (screen reader integration)

**Running the application:**

Since `conda run` may not work in Git Bash on Windows, use direct Python path:

```bash
# Find environment location first
conda env list

# Run using direct path (Git Bash on Windows)
~/.conda/envs/ENVNAME/python.exe SpaceAtless.py

# Or use conda run if available (PowerShell)
conda run -n ENVNAME python SpaceAtless.py
```

See `conda.md` for comprehensive conda environment guidance.

## Architecture

### Module Structure

```
SpaceAtless/
├── SpaceAtless.py          # Main entry point, pygame loop, UI rendering
├── config.json             # User preferences (mode setting)
├── data/
│   └── celestial_objects.json  # Catalog of all celestial objects
├── models/
│   ├── celestial_object.py     # CelestialObject class (position, sound, announcement)
│   └── celestial_database.py   # JSON catalog loader and query interface
├── engine/
│   ├── audio_engine.py         # 3D spatial audio generation (core audio pipeline)
│   ├── config_manager.py       # User mode management (Educational/Exploration/Advanced)
│   └── navigation_controller.py # Spatial navigation logic
├── ui/
│   └── speech_handler.py       # Async speech queue using Cytolk/Tolk
└── utils/
    └── api_client.py           # NASA Horizons API client
```

### Core Architecture Patterns

**1. Data Flow: API → CelestialObject → AudioEngine → Pygame**

Objects are fetched from NASA Horizons API, converted to `CelestialObject` instances with 3D coordinates (x, y, z in AU), then spatial audio is generated based on position and user mode.

**2. Mode-Based Configuration**

The `ConfigManager` (engine/config_manager.py) drives three distinct experiences:
- **Educational**: Verbose announcements, simple mono audio, detailed help
- **Exploration**: Balanced announcements, stereo panning
- **Advanced**: Concise announcements, full 3D audio (stereo + depth filters + reverb)

Audio complexity is controlled by `audio_params` from ConfigManager:
- `simple`: Volume attenuation only
- `moderate`: Stereo panning + volume
- `complex`: Full pipeline (low-pass filter, stereo, reverb, volume)

**3. Audio Pipeline (AudioEngine)**

The audio engine (engine/audio_engine.py) generates spatial audio through a multi-stage pipeline:

```
generate_tone() → apply_low_pass_filter() → apply_stereo_panning()
  → apply_reverb() → apply_volume_attenuation() → pygame.mixer.Sound
```

- Stereo panning uses constant-power law for smooth L/R positioning
- Low-pass filtering simulates air absorption (distant objects sound muffled)
- Reverb uses delay + decay based on Z-axis depth
- Volume uses inverse square law with clamping

**4. Threading Model**

- **Main thread**: Pygame event loop, rendering, audio playback
- **Speech thread**: Async speech queue (SpeechHandler) for screen reader output
- **Data fetch threads**:
  - Initial background fetch on startup
  - Periodic hourly updates

All threads use locks to protect the shared `celestial_objects` list.

**5. Navigation System**

Two navigation modes managed by NavigationController:
- **Spatial mode**: Arrow keys move to nearest object in that direction (2D screen space)
- **Jump mode**: Press 'J' to enter list navigation, select with Enter

Spatial navigation uses screen coordinates (calculated from 3D positions via projection).

### NASA Horizons API Integration

The API client (utils/api_client.py) queries JPL Horizons with:
- EPHEM_TYPE=VECTORS for Cartesian coordinates
- CENTER='@sun' for heliocentric positions
- OUT_UNITS='AU-D' for astronomical units
- REF_PLANE='ECLIPTIC' for standard solar system reference

Object definitions in `data/celestial_objects.json` map names to Horizons command codes (e.g., "199" for Mercury, "-31" for Voyager 1).

### Celestial Database System

The database (models/celestial_database.py) loads from JSON and supports:
- **Category filtering**: Only load specific categories (planets, moons, etc.)
- **Search**: By name, type, or category
- **Dynamic loading**: Add/remove categories at runtime
- **Custom objects**: Add objects not in the catalog

Default active categories: `["planets", "dwarf_planets", "moons", "spacecraft"]`

## Common Development Commands

### Running the Application

```bash
# Using direct conda environment path (Git Bash)
~/.conda/envs/ENVNAME/python.exe SpaceAtless.py

# Using conda run (PowerShell)
conda run -n ENVNAME python SpaceAtless.py
```

### Installing Dependencies

```bash
# Install all required packages
conda run -n ENVNAME pip install pygame numpy scipy requests cytolk
```

### Testing Audio Engine

To test audio generation without the full UI, you can import and use AudioEngine directly:

```python
from engine.audio_engine import AudioEngine
from engine.config_manager import ConfigManager

audio_engine = AudioEngine()
config_manager = ConfigManager()
audio_params = config_manager.get_audio_params()

# Generate spatial sound
sound = audio_engine.create_spatial_sound(
    obj_type="Planet",
    x=1.0, y=0.5, z=0.2,
    distance=1.5,
    audio_params=audio_params
)
sound.play()
```

### Modifying the Celestial Catalog

Edit `data/celestial_objects.json` to add/remove objects. Structure:

```json
{
  "categories": {
    "category_name": [
      {
        "name": "Object Name",
        "command": "horizons_id",
        "type": "Planet|Moon|Asteroid|Comet|Spacecraft|Dwarf Planet",
        "size": 8,
        "description": "Optional description"
      }
    ]
  }
}
```

Find Horizons command codes at: https://ssd.jpl.nasa.gov/horizons/

## Key Implementation Details

### Audio Generation Specifics

**Base frequencies by object type** (musical notes):
- Planet: 440 Hz (A4)
- Moon: 523.25 Hz (C5)
- Asteroid: 587.33 Hz (D5)
- Comet: 659.25 Hz (E5)
- Spacecraft: 784 Hz (G5)
- Dwarf Planet: 493.88 Hz (B4)

Frequency is modulated by distance: `freq = base_freq + (distance * 10)`

**Stereo panning** uses constant-power panning law:
- Pan angle = (x_position / max_distance) * π/4
- Left gain = cos(pan_angle)
- Right gain = sin(pan_angle)

**Low-pass filter cutoff**: `max(200, 8000 - (distance * 500))` Hz

### Screen Reader Integration

Speech is handled asynchronously via `SpeechHandler` thread:
- Messages queued via `speech_queue.put(message)`
- Cytolk/Tolk library speaks messages in background
- If Cytolk unavailable, messages logged instead

The app gracefully degrades if screen reader support is unavailable.

### Keyboard Controls

- **Arrow keys**: Navigate spatially between objects
- **J**: Enter jump/list mode
- **M**: Cycle through user modes (Educational → Exploration → Advanced)
- **Enter** (in jump mode): Select object
- **Up/Down** (in jump mode): Navigate list

### Configuration Persistence

User mode preference is saved to `config.json` as:

```json
{
  "user_mode": "educational|exploration|advanced"
}
```

Loaded on startup by ConfigManager.

## Important Notes for Development

### Adding New Celestial Objects

1. Add definition to `data/celestial_objects.json` in appropriate category
2. Include Horizons command code (find via JPL Horizons web interface)
3. Restart application (or implement hot-reload in future)

### Modifying Audio Behavior

The audio pipeline is in `AudioEngine.create_spatial_sound()`. To change audio characteristics:
- Adjust base frequencies in `self.base_frequencies`
- Modify filter parameters in `apply_low_pass_filter()`
- Change reverb settings in `apply_reverb()`
- Update volume curve in `apply_volume_attenuation()`

### Changing User Mode Behavior

Edit `ConfigManager.mode_configs` dictionary to modify:
- Announcement verbosity
- Help level detail
- Sound complexity
- Audio cue presence

### Threading Considerations

When modifying celestial_objects list:
- Always acquire `lock` before read/write
- Keep critical sections short
- Sound generation can be slow - keep it outside locks when possible

### Screen Resolution

Current screen size is hardcoded: WIDTH=1200, HEIGHT=800 (in both SpaceAtless.py and celestial_object.py). To change, update both constants and the projection scaling in `calculate_screen_position()`.

## External Dependencies

### DLL Files

The project includes Windows DLLs for screen reader integration:
- `nvdaControllerClient64.dll`: NVDA screen reader support
- `SAAPI64.dll`: System Access/JAWS screen reader support

These are used by the Cytolk library for multi-screen-reader compatibility.

### NASA JPL Horizons API

API endpoint: `https://ssd.jpl.nasa.gov/api/horizons.api`

The API is free and does not require authentication. Rate limits are generous but consider caching for development to avoid repeated calls.

**Note**: The API periodically updates object positions. The app fetches data hourly in the background thread.

## Testing Recommendations

### Manual Testing Checklist

1. **Mode switching**: Press 'M' and verify announcements change verbosity
2. **Audio complexity**: Listen for stereo panning (Exploration) vs reverb (Advanced)
3. **Navigation**: Test all arrow keys and jump mode
4. **Data loading**: Check console for successful API fetches
5. **Screen reader**: Verify speech output if Cytolk available

### Common Issues

**Audio not playing**: Check pygame.mixer initialization and sample rate (44100 Hz)

**API fetch failures**: Verify internet connection and check Horizons API status

**Screen reader not working**: Ensure Cytolk installed and screen reader running

**Performance issues**: Reduce number of objects in catalog or simplify audio mode

## File References

When discussing code with Claude, reference functions using this format:

- Main loop: `SpaceAtless.py:165` (main game loop)
- Audio generation: `engine/audio_engine.py:187` (create_spatial_sound)
- Mode switching: `engine/config_manager.py:139` (cycle_mode)
- API fetching: `utils/api_client.py:16` (fetch_celestial_objects)
- Navigation logic: `engine/navigation_controller.py:28` (get_next_spatial_object)
