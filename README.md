# Accessible Space Atlas

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Accessibility](https://img.shields.io/badge/accessibility-NVDA%20%7C%20JAWS-green.svg)](https://www.nvaccess.org/)

An accessible audio space exploration application that uses 3D spatial sound and screen reader support to help blind and visually impaired users navigate the solar system.

## Features

- **3D Spatial Audio**: Celestial objects are positioned in stereo space with distance-based effects
- **Screen Reader Integration**: Full support for NVDA and JAWS via Cytolk
- **Three User Modes**: Educational (verbose), Exploration (balanced), Advanced (concise)
- **Real-time NASA Data**: Fetches live positions from NASA JPL Horizons API
- **Space Weather Alerts**: Monitors solar flares, CMEs, and geomagnetic storms from NASA DONKI
- **Orbital Hierarchy Audio**: Hear moons relative to their planets, not just the Sun
- **Offline Support**: Caches data for use without internet connection

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Conda (recommended) or pip
- A screen reader (NVDA or JAWS) for full accessibility

### Installation

```bash
# Clone the repository
git clone https://github.com/taljazz/AccessibleSpaceAtlas.git
cd AccessibleSpaceAtlas

# Create conda environment
conda create -n spaceatlass python=3.11
conda activate spaceatlass

# Install dependencies
pip install -r requirements.txt

# Run the application
python SpaceAtless.py
```

### Alternative: Direct pip install

```bash
pip install pygame numpy scipy requests cytolk
python SpaceAtless.py
```

## Keyboard Controls

| Key | Action |
|-----|--------|
| **Arrow Keys** | Navigate between objects spatially |
| **J** | Enter jump mode (list navigation) |
| **M** | Cycle user modes (Educational/Exploration/Advanced) |
| **F** | Filter by object type |
| **S** | Search for objects by name |
| **H** | Hear help message |

### Bookmarks
| Key | Action |
|-----|--------|
| **B** | Bookmark current object |
| **0-9** | Recall bookmark (0 = slot 10) |
| **Shift+0-9** | Save to specific bookmark slot |
| **Shift+B** | List all bookmarks |

### Information
| Key | Action |
|-----|--------|
| **U** | Cycle distance units (A U / km / miles) |
| **V** | Announce object velocity |
| **R** | Distance to reference object |
| **Shift+R** | Set current object as reference |

### View Controls
| Key | Action |
|-----|--------|
| **Page Up** | Zoom in |
| **Page Down** | Zoom out |
| **Home** | Reset zoom |
| **L** | Toggle follow mode |

### Audio & Time
| Key | Action |
|-----|--------|
| **O** | Toggle orbital/absolute audio positioning |
| **C** | Cluster focus (amplify moons of selected planet) |
| **T** | Change time scale |
| **P** | Pause/resume orbital motion |
| **- / =** | Decrease/increase volume |

### Other
| Key | Action |
|-----|--------|
| **W** | Check space weather |
| **E** | Export objects to CSV |

## User Modes

1. **Educational**: Detailed descriptions, simple audio, helpful hints - perfect for learning
2. **Exploration**: Balanced information with stereo panning - ideal for browsing
3. **Advanced**: Concise data with full 3D audio (filtering, reverb, panning) - for experienced users

## Data Sources

- **Celestial Positions**: [NASA JPL Horizons System](https://ssd.jpl.nasa.gov/horizons/)
- **Space Weather**: [NASA DONKI API](https://ccmc.gsfc.nasa.gov/donki/)

## Accessibility Notes

This application is designed from the ground up for blind and visually impaired users:

- All information is conveyed through speech and spatial audio
- Screen reader announcements adapt to user mode verbosity
- No visual-only information - everything is accessible
- Keyboard-only navigation throughout

### Screen Reader Setup

The app uses [Cytolk](https://pypi.org/project/cytolk/) for screen reader integration. It automatically detects and works with:
- NVDA
- JAWS
- System Access
- Window-Eyes

If no screen reader is detected, announcements are logged to the console.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- NASA JPL for the Horizons API
- NASA CCMC for the DONKI space weather API
- The blind and visually impaired community for inspiration and feedback
