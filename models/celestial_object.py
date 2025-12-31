"""
Celestial object model.
Represents a celestial body with position, type, and visual properties.
"""
import pygame
import numpy as np
from scipy.io import wavfile
from io import BytesIO
import queue


# Screen settings (imported from main - will be passed in later refactor)
WIDTH, HEIGHT = 1200, 800


class CelestialObject:
    """Represents a celestial body in space."""

    def __init__(self, name, type_, x, y, z, size, distance, vx=0.0, vy=0.0, vz=0.0, parent=None, generate_sound=True):
        self.name = name
        self.type = type_  # 'Planet', 'Asteroid', 'Comet', 'Spacecraft'
        self.x = x  # Cartesian coordinates in AU (absolute heliocentric)
        self.y = y
        self.z = z
        self.vx = vx  # Velocity in AU/day
        self.vy = vy
        self.vz = vz
        self.parent = parent  # Parent object name (e.g., "Sun", "Earth", "Jupiter")
        self.size = size  # For rendering
        self.distance = distance  # From observer in AU
        self.screen_pos = self.calculate_screen_position()
        # Sound will be set by AudioEngine or generated locally
        self.sound = self.generate_sound() if generate_sound else None

    def calculate_screen_position(self):
        """Calculate 2D screen position from 3D coordinates."""
        # Simple scaling for visualization
        scale = 500  # Adjust as needed for visibility
        screen_x = WIDTH // 2 + int(self.x * scale)
        screen_y = HEIGHT // 2 - int(self.y * scale)
        return (screen_x, screen_y)

    def update_position(self, time_scale=1.0):
        """
        Update object position based on velocity.

        Args:
            time_scale: Time multiplier (1.0 = real-time, 100.0 = 100x faster, etc.)
                       Velocity is in AU/day, so time_scale represents how many days
                       pass per second of real time.
        """
        # Update position: new_pos = old_pos + velocity * time_delta
        # time_delta is in days (time_scale / FPS)
        # At 30 FPS with time_scale=1.0: each frame = 1/30 day = ~48 minutes
        time_delta = time_scale / 30.0  # Assuming 30 FPS

        self.x += self.vx * time_delta
        self.y += self.vy * time_delta
        self.z += self.vz * time_delta

        # Recalculate derived values
        self.distance = (self.x**2 + self.y**2 + self.z**2) ** 0.5
        self.screen_pos = self.calculate_screen_position()

    def generate_sound(self):
        """
        Generate a simple tone based on the object's distance and type.
        Uses safe frequencies and shorter duration.

        NOTE: This is a fallback method. AudioEngine is preferred.
        """
        duration = 0.2  # Shortened to 0.2 seconds for less intrusive audio

        # Safe volume calculation (max 60%, min 5%)
        volume = 1.0 / max(0.5, self.distance ** 2)
        volume = min(0.6, max(0.05, volume))

        # Base frequency for types
        base_freq = {
            "Star": 220.0,        # A3 (low, powerful)
            "Planet": 440,        # A4
            "Moon": 523.25,       # C5
            "Asteroid": 587.33,   # D5
            "Comet": 659.25,      # E5
            "Spacecraft": 784.00, # G5
            "Dwarf Planet": 493.88  # B4
        }.get(self.type, 440)  # Default to 440 Hz if type unknown

        # Use logarithmic scaling for distance to keep frequencies safe
        distance_factor = np.log1p(self.distance) * 50
        freq = base_freq + distance_factor

        # Clamp to safe hearing range (100 Hz - 2000 Hz)
        freq = np.clip(freq, 100.0, 2000.0)

        sample_rate = 44100  # Samples per second
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        note = np.sin(freq * t * 2 * np.pi)

        # Apply fade-in and fade-out to prevent clicks
        fade_samples = int(sample_rate * 0.02)  # 20ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        note[:fade_samples] *= fade_in
        note[-fade_samples:] *= fade_out

        # Normalize to 16-bit range
        audio = note * (2**15 - 1) / np.max(np.abs(note))
        audio = audio.astype(np.int16)

        # Convert to bytes
        sound_buffer = BytesIO()
        wavfile.write(sound_buffer, sample_rate, audio)
        sound_buffer.seek(0)
        sound = pygame.mixer.Sound(sound_buffer)
        sound.set_volume(volume)
        return sound

    def set_sound(self, sound):
        """
        Set the object's sound (from AudioEngine).

        Args:
            sound: pygame.mixer.Sound object
        """
        self.sound = sound

    def play_sound(self):
        """Play the object's audio tone."""
        if self.sound:
            self.sound.play()

    def announce(self, speech_queue: queue.Queue, config_manager=None):
        """
        Announce the object via screen reader.

        Args:
            speech_queue: Queue for speech messages
            config_manager: Optional ConfigManager for mode-specific announcements
        """
        if config_manager:
            announcement = config_manager.get_announcement_template(self)
        else:
            # Fallback to default announcement
            announcement = f"{self.type}: {self.name}, Distance: {self.distance:.2f} astronomical units."

        speech_queue.put(announcement)

    def to_dict(self):
        """Convert object to dictionary (for serialization)."""
        return {
            "name": self.name,
            "type": self.type,
            "x": self.x,
            "y": self.y,
            "z": self.z,
            "size": self.size,
            "distance": self.distance
        }
