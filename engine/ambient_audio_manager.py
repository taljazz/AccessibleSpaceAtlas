"""
Ambient audio streaming manager for space sounds.
Streams audio from NASA, University of Iowa plasma waves, and ISS live feeds.
"""

import pygame
import threading
import requests
import logging
import queue
import tempfile
import os
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path


class StreamState(Enum):
    """States for the ambient audio stream."""
    STOPPED = "stopped"
    LOADING = "loading"
    PLAYING = "playing"
    ERROR = "error"


class AmbientAudioManager:
    """
    Manages streaming ambient space audio for celestial objects.

    Uses pygame.mixer.music for streaming (supports MP3, OGG) and
    operates independently from navigation sounds.
    """

    def __init__(self, speech_queue: queue.Queue, config_manager):
        """
        Initialize ambient audio manager.

        Args:
            speech_queue: Queue for screen reader announcements
            config_manager: ConfigManager for preferences
        """
        self.speech_queue = speech_queue
        self.config_manager = config_manager

        # State tracking
        self._enabled: bool = False
        self._state: StreamState = StreamState.STOPPED
        self._current_object_name: Optional[str] = None
        self._current_url: Optional[str] = None
        self._loading_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Audio source mappings
        self._audio_sources: Dict[str, Dict[str, Any]] = {}
        self._load_audio_sources()

        # Temp file for downloaded audio
        self._temp_file: Optional[str] = None

        # Volume (0.0 to 1.0)
        self._volume: float = 0.5

        logging.info("AmbientAudioManager initialized")

    def _load_audio_sources(self) -> None:
        """Load audio source mappings from JSON file or use defaults."""
        try:
            from engine.config_manager import get_base_path
            base_path = get_base_path()
            sources_file = base_path / "data" / "ambient_audio_sources.json"

            if sources_file.exists():
                import json
                with open(sources_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._audio_sources = data.get('sources', {})
                logging.info(f"Loaded {len(self._audio_sources)} ambient audio sources")
            else:
                logging.info("No ambient_audio_sources.json found, using defaults")
                self._setup_default_sources()
        except Exception as e:
            logging.error(f"Failed to load audio sources: {e}")
            self._setup_default_sources()

    def _setup_default_sources(self) -> None:
        """Set up default audio source mappings."""
        self._audio_sources = {
            # Jupiter - Juno bow shock crossing
            "Jupiter": {
                "url": "https://space.physics.uiowa.edu/plasma-wave/juno/audio/201606/jno-bshock-16-176-0700-0900-blk.mp3",
                "type": "plasma_wave",
                "description": "Juno spacecraft recording of Jupiter's bow shock"
            },
            # Europa flyby
            "Europa": {
                "url": "https://space.physics.uiowa.edu/plasma-wave/juno/audio/202209/jno-E45-LFRH-22-272-0836-1006-1st-try-Matlab-modified.mp3",
                "type": "plasma_wave",
                "description": "Juno Europa flyby plasma wave recordings"
            },
            # Earth - Van Allen Probes
            "Earth": {
                "url": "https://space.physics.uiowa.edu/plasma-wave/rbsp/audio/201904/VanA-2019-04-30-0054.mp3",
                "type": "plasma_wave",
                "description": "Van Allen Probes recordings of Earth's radiation belts"
            },
            # Sun - use Earth's solar wind data as proxy
            "Sun": {
                "url": "https://space.physics.uiowa.edu/plasma-wave/rbsp/audio/201904/VanA-2019-04-30-0054.mp3",
                "type": "plasma_wave",
                "description": "Solar wind plasma recordings"
            },
        }

    @property
    def is_enabled(self) -> bool:
        """Check if ambient audio is enabled."""
        return self._enabled

    @property
    def state(self) -> StreamState:
        """Get current stream state."""
        return self._state

    def toggle(self, current_object: Any = None) -> bool:
        """
        Toggle ambient audio on/off.

        Args:
            current_object: Currently selected CelestialObject

        Returns:
            True if now enabled, False if now disabled
        """
        if self._enabled:
            self.stop()
            self._enabled = False
            self.speech_queue.put("Ambient audio disabled.")
            logging.info("Ambient audio disabled")
            return False
        else:
            self._enabled = True
            logging.info("Ambient audio enabled")
            if current_object:
                self.play_for_object(current_object)
            else:
                self.speech_queue.put("Ambient audio enabled. Navigate to an object to hear space sounds.")
            return True

    def play_for_object(self, celestial_object: Any) -> bool:
        """
        Start playing ambient audio for a celestial object.

        Args:
            celestial_object: CelestialObject to play audio for

        Returns:
            True if audio started loading, False if no audio available
        """
        if not self._enabled:
            return False

        object_name = celestial_object.name

        # Check if already playing this object
        if self._current_object_name == object_name and self._state == StreamState.PLAYING:
            return True

        # Stop current playback
        self.stop()

        # Look up audio source
        audio_info = self._get_audio_source(celestial_object)

        if audio_info is None:
            self._announce_no_audio(celestial_object)
            return False

        # Start loading in background
        self._current_object_name = object_name
        self._current_url = audio_info['url']
        self._state = StreamState.LOADING

        self.speech_queue.put(f"Loading ambient audio for {object_name}...")
        logging.info(f"Loading ambient audio for {object_name}: {audio_info['url']}")

        # Start background loading thread
        self._stop_event.clear()
        self._loading_thread = threading.Thread(
            target=self._load_and_play,
            args=(audio_info,),
            daemon=True
        )
        self._loading_thread.start()

        return True

    def _get_audio_source(self, celestial_object: Any) -> Optional[Dict[str, Any]]:
        """
        Find audio source for a celestial object.

        Checks in order:
        1. Direct object match
        2. Parent object match (for moons/spacecraft)
        3. Type-based defaults

        Args:
            celestial_object: The object to find audio for

        Returns:
            Audio source info dict or None if not found
        """
        # Direct match by name
        if celestial_object.name in self._audio_sources:
            return self._audio_sources[celestial_object.name]

        # Check parent (e.g., moon of Jupiter uses Jupiter audio)
        parent = getattr(celestial_object, 'parent', None)
        if parent and parent in self._audio_sources:
            return self._audio_sources[parent]

        # For spacecraft, check if near a planet with audio
        if celestial_object.type == "Spacecraft":
            # Check common parent planets
            for planet in ["Jupiter", "Saturn", "Earth", "Mars"]:
                if parent == planet and planet in self._audio_sources:
                    return self._audio_sources[planet]

        return None

    def _load_and_play(self, audio_info: Dict[str, Any]) -> None:
        """
        Background thread to load and play audio stream.

        Args:
            audio_info: Dict with url, type, description
        """
        try:
            url = audio_info['url']
            audio_type = audio_info.get('type', 'unknown')

            if audio_type == 'live_stream':
                # For live streams, try direct URL loading
                self._play_live_stream(url)
            else:
                # For files, download and play
                self._download_and_play(url)

        except Exception as e:
            if not self._stop_event.is_set():
                logging.error(f"Error loading ambient audio: {e}")
                self._state = StreamState.ERROR
                self.speech_queue.put(f"Failed to load audio. Check internet connection.")

    def _download_and_play(self, url: str) -> None:
        """Download audio file and play it."""
        try:
            # Download with timeout
            logging.info(f"Downloading: {url}")
            response = requests.get(url, timeout=30, stream=True)
            response.raise_for_status()

            if self._stop_event.is_set():
                return

            # Save to temp file (pygame.mixer.music needs file path or file-like object)
            # Create temp file with appropriate extension
            ext = '.mp3' if url.endswith('.mp3') else '.wav' if url.endswith('.wav') else '.ogg'
            fd, temp_path = tempfile.mkstemp(suffix=ext)

            try:
                with os.fdopen(fd, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if self._stop_event.is_set():
                            os.unlink(temp_path)
                            return
                        f.write(chunk)

                # Store temp file path for cleanup
                self._temp_file = temp_path

                if self._stop_event.is_set():
                    return

                # Play the audio
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.set_volume(self._volume)
                pygame.mixer.music.play(loops=-1)  # Loop indefinitely

                self._state = StreamState.PLAYING
                self.speech_queue.put(f"Now playing: {self._current_object_name} space sounds.")
                logging.info(f"Playing ambient audio for {self._current_object_name}")

            except pygame.error as e:
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                raise Exception(f"Playback error: {e}")

        except requests.exceptions.Timeout:
            raise Exception("Download timed out")
        except requests.exceptions.RequestException as e:
            raise Exception(f"Network error: {e}")

    def _play_live_stream(self, url: str) -> None:
        """Play a live audio stream."""
        try:
            # pygame.mixer.music can sometimes stream from URL
            pygame.mixer.music.load(url)
            pygame.mixer.music.set_volume(self._volume)
            pygame.mixer.music.play()

            self._state = StreamState.PLAYING
            self.speech_queue.put(f"Connected to live stream: {self._current_object_name}.")
            logging.info(f"Playing live stream for {self._current_object_name}")

        except pygame.error as e:
            raise Exception(f"Live stream error: {e}")

    def _announce_no_audio(self, celestial_object: Any) -> None:
        """Announce that no ambient audio is available."""
        mode = self.config_manager.get_current_mode()

        if mode == 'educational':
            available = ", ".join(self._audio_sources.keys())
            self.speech_queue.put(
                f"No ambient audio available for {celestial_object.name}. "
                f"Space sounds are available for: {available}."
            )
        elif mode == 'exploration':
            self.speech_queue.put(f"No ambient audio for {celestial_object.name}.")
        else:  # advanced
            self.speech_queue.put("No audio available.")

    def stop(self) -> None:
        """Stop current audio playback."""
        self._stop_event.set()

        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception:
            pass

        # Cleanup temp file
        if self._temp_file and os.path.exists(self._temp_file):
            try:
                os.unlink(self._temp_file)
            except Exception:
                pass
            self._temp_file = None

        self._state = StreamState.STOPPED
        self._current_object_name = None
        self._current_url = None

    def set_volume(self, volume: float) -> None:
        """
        Set ambient audio volume.

        Args:
            volume: Volume level 0.0 to 1.0 (will be scaled to 50% max)
        """
        self._volume = max(0.0, min(1.0, volume * 0.5))  # Cap at 50%
        try:
            pygame.mixer.music.set_volume(self._volume)
        except Exception:
            pass

    def get_status_announcement(self) -> str:
        """Get current status for screen reader."""
        if not self._enabled:
            return "Ambient audio disabled. Press A to enable."

        if self._state == StreamState.PLAYING:
            return f"Playing ambient audio for {self._current_object_name}."
        elif self._state == StreamState.LOADING:
            return f"Loading audio for {self._current_object_name}..."
        elif self._state == StreamState.ERROR:
            return "Ambient audio encountered an error."
        else:
            return "Ambient audio enabled. Navigate to an object to hear space sounds."

    def shutdown(self) -> None:
        """Cleanup on application exit."""
        logging.info("Shutting down AmbientAudioManager")
        self.stop()
