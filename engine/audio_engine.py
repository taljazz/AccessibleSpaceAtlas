"""
Audio engine for 3D spatial audio generation.
Implements stereo panning, depth effects, and mode-specific audio complexity.
"""
import numpy as np
from scipy.io import wavfile
from scipy.signal import butter, filtfilt
from io import BytesIO
import pygame
import logging


class AudioEngine:
    """Generates 3D spatial audio for celestial objects."""

    def __init__(self, sample_rate=44100, enable_cache=True):
        """
        Initialize the audio engine.

        Args:
            sample_rate: Audio sample rate in Hz (default 44100)
            enable_cache: Whether to enable audio caching (default True)
        """
        self.sample_rate = sample_rate
        self.max_distance = 40.0  # Maximum distance in AU for normalization
        self.enable_cache = enable_cache

        # Audio cache: key -> pygame.mixer.Sound
        # Key format: (obj_type, distance_bucket, complexity, pan_bucket)
        self._audio_cache = {}
        self._cache_hits = 0
        self._cache_misses = 0

        # Base frequencies for different object types (musical notes)
        self.base_frequencies = {
            "Star": 220.0,          # A3 (low, powerful)
            "Planet": 440.0,        # A4
            "Moon": 523.25,         # C5
            "Asteroid": 587.33,     # D5
            "Comet": 659.25,        # E5
            "Spacecraft": 784.00,   # G5
            "Dwarf Planet": 493.88  # B4
        }

    def _get_cache_key(self, obj_type, x, distance, complexity):
        """
        Generate cache key for audio lookup.
        Uses buckets to allow similar sounds to share cache entries.

        Args:
            obj_type: Type of celestial object
            x: X position for panning
            distance: Distance from observer in AU
            complexity: Audio complexity setting

        Returns:
            Tuple cache key
        """
        # Bucket distance into 0.5 AU increments (0-40 AU = 80 buckets)
        distance_bucket = int(min(distance, 40.0) * 2)

        # Bucket panning into 10 positions (-5 to +5)
        pan_bucket = int(np.clip(x / self.max_distance * 5, -5, 5))

        return (obj_type, distance_bucket, complexity, pan_bucket)

    def get_cache_stats(self):
        """Get cache statistics for debugging."""
        total = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total * 100) if total > 0 else 0
        return {
            'cache_size': len(self._audio_cache),
            'hits': self._cache_hits,
            'misses': self._cache_misses,
            'hit_rate': f"{hit_rate:.1f}%"
        }

    def clear_cache(self):
        """Clear the audio cache."""
        self._audio_cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logging.info("Audio cache cleared")

    def generate_tone(self, obj_type, distance, duration=0.2):
        """
        Generate a basic mono tone for an object with safe frequencies.

        Args:
            obj_type: Type of celestial object
            distance: Distance from observer in AU
            duration: Sound duration in seconds (default 0.2s for brevity)

        Returns:
            Numpy array containing mono audio samples
        """
        # Get base frequency for this object type
        base_freq = self.base_frequencies.get(obj_type, 440.0)

        # Modulate frequency based on distance (but keep it safe)
        # Use logarithmic scaling for distance to prevent extreme frequencies
        distance_factor = np.log1p(distance) * 50  # log1p(x) = log(1+x), safer for distance=0
        freq = base_freq + distance_factor

        # Clamp frequency to safe, comfortable hearing range (100 Hz - 2000 Hz)
        freq = np.clip(freq, 100.0, 2000.0)

        # Generate sine wave
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)
        audio = np.sin(freq * t * 2 * np.pi)

        # Apply fade-in and fade-out envelope to prevent clicks
        fade_samples = int(self.sample_rate * 0.02)  # 20ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)

        audio[:fade_samples] *= fade_in
        audio[-fade_samples:] *= fade_out

        return audio

    def apply_stereo_panning(self, audio_mono, x_position):
        """
        Apply stereo panning based on X-axis position.
        Uses constant-power panning law for smooth transitions.

        Args:
            audio_mono: 1D numpy array (mono audio)
            x_position: Object's X coordinate in AU

        Returns:
            2D numpy array with shape (samples, 2) for stereo
        """
        # Normalize x_position to [-1, 1] range
        pan = np.clip(x_position / self.max_distance, -1.0, 1.0)

        # Constant power panning law (maintains perceived loudness)
        # Pan angle from -45° (left) to +45° (right)
        pan_angle = pan * np.pi / 4

        # Calculate channel gains
        left_gain = np.cos(pan_angle)
        right_gain = np.sin(pan_angle)

        # Apply gains to create stereo
        left_channel = audio_mono * left_gain
        right_channel = audio_mono * right_gain

        # Stack into stereo array
        stereo_audio = np.column_stack((left_channel, right_channel))

        return stereo_audio

    def apply_low_pass_filter(self, audio, distance):
        """
        Apply low-pass filter to simulate air absorption.
        Distant objects sound more muffled.

        Args:
            audio: Audio array (mono or stereo)
            distance: Distance in AU

        Returns:
            Filtered audio array
        """
        # Calculate cutoff frequency based on distance
        # Close objects: 8kHz, Distant objects: 200Hz
        cutoff_freq = max(200, 8000 - (distance * 500))

        # Normalize to Nyquist frequency
        nyquist = self.sample_rate / 2
        normalized_cutoff = min(cutoff_freq / nyquist, 0.99)  # Ensure < 1.0

        try:
            # 4th order Butterworth low-pass filter
            b, a = butter(4, normalized_cutoff, btype='low')

            # Apply filter (handle both mono and stereo)
            if audio.ndim == 1:
                # Mono
                filtered = filtfilt(b, a, audio)
            else:
                # Stereo - filter each channel
                filtered = np.zeros_like(audio)
                for ch in range(audio.shape[1]):
                    filtered[:, ch] = filtfilt(b, a, audio[:, ch])

            return filtered
        except Exception as e:
            logging.warning(f"Low-pass filter failed: {e}. Returning unfiltered audio.")
            return audio

    def apply_reverb(self, audio, z_position, distance):
        """
        Apply simple reverb (delay + decay) based on depth.

        Args:
            audio: Audio array
            z_position: Z-axis position (depth)
            distance: Distance in AU

        Returns:
            Audio with reverb applied
        """
        # Calculate reverb parameters
        # Delay: 50-150ms based on Z-axis
        reverb_delay_ms = int(50 + abs(z_position) * 20)
        reverb_delay_ms = np.clip(reverb_delay_ms, 50, 150)
        reverb_samples = int(reverb_delay_ms * self.sample_rate / 1000)

        # Decay: More decay for distant objects
        reverb_decay = 0.3 + (distance * 0.05)
        reverb_decay = np.clip(reverb_decay, 0.3, 0.7)

        # Apply reverb
        reverb_audio = np.copy(audio)

        if audio.ndim == 1:
            # Mono reverb
            if len(reverb_audio) > reverb_samples:
                reverb_audio[reverb_samples:] += audio[:-reverb_samples] * reverb_decay
        else:
            # Stereo reverb
            if len(reverb_audio) > reverb_samples:
                reverb_audio[reverb_samples:] += audio[:-reverb_samples] * reverb_decay

        return reverb_audio

    def apply_volume_attenuation(self, audio, distance):
        """
        Apply distance-based volume attenuation with safety limits.
        Uses inverse square law, clamped for usability and hearing safety.

        Args:
            audio: Audio array
            distance: Distance in AU

        Returns:
            Audio with volume adjusted
        """
        # Inverse square law with minimum distance
        distance_attenuation = 1.0 / max(0.5, distance ** 2)

        # Clamp to safe, comfortable range
        # Max 0.6 (60%) to prevent loud sounds, min 0.05 (5%) for very distant objects
        distance_attenuation = np.clip(distance_attenuation, 0.05, 0.6)

        return audio * distance_attenuation

    def create_spatial_sound(self, obj_type, x, y, z, distance, audio_params):
        """
        Main pipeline for creating 3D spatial audio with safety features.
        Uses caching to improve performance.

        Args:
            obj_type: Type of celestial object
            x, y, z: 3D position in AU
            distance: Distance from observer in AU
            audio_params: Dictionary from ConfigManager with complexity settings

        Returns:
            pygame.mixer.Sound object ready for playback
        """
        complexity = audio_params.get('complexity', 'moderate')
        duration = 0.2  # Shortened duration for less intrusive audio

        # Check cache first
        if self.enable_cache:
            cache_key = self._get_cache_key(obj_type, x, distance, complexity)
            if cache_key in self._audio_cache:
                self._cache_hits += 1
                return self._audio_cache[cache_key]
            self._cache_misses += 1

        # Step 1: Generate base tone
        audio_mono = self.generate_tone(obj_type, distance, duration)

        # Step 2: Apply effects based on complexity mode
        if complexity == 'simple':
            # Educational mode: Just basic volume, mono output
            audio_mono = self.apply_volume_attenuation(audio_mono, distance)
            # Convert mono to stereo (same in both channels)
            audio_stereo = np.column_stack((audio_mono, audio_mono))

        elif complexity == 'moderate':
            # Exploration mode: Stereo panning + volume
            audio_stereo = self.apply_stereo_panning(audio_mono, x)
            audio_stereo = self.apply_volume_attenuation(audio_stereo, distance)

        else:  # 'complex'
            # Advanced mode: Full 3D audio pipeline
            # Apply depth effects to mono first
            audio_mono = self.apply_low_pass_filter(audio_mono, distance)

            # Apply stereo panning
            audio_stereo = self.apply_stereo_panning(audio_mono, x)

            # Apply reverb
            audio_stereo = self.apply_reverb(audio_stereo, z, distance)

            # Apply volume attenuation
            audio_stereo = self.apply_volume_attenuation(audio_stereo, distance)

        # Step 3: Normalize and convert to 16-bit PCM
        # Prevent clipping
        max_val = np.max(np.abs(audio_stereo))
        if max_val > 0:
            audio_stereo = audio_stereo / max_val

        # Convert to 16-bit integer
        audio_int16 = (audio_stereo * (2**15 - 1)).astype(np.int16)

        # Step 4: Create pygame Sound object
        sound_buffer = BytesIO()
        wavfile.write(sound_buffer, self.sample_rate, audio_int16)
        sound_buffer.seek(0)

        try:
            sound = pygame.mixer.Sound(sound_buffer)

            # Cache the sound for future use
            if self.enable_cache:
                cache_key = self._get_cache_key(obj_type, x, distance, complexity)
                self._audio_cache[cache_key] = sound

            return sound
        except Exception as e:
            logging.error(f"Failed to create pygame Sound: {e}")
            # Return a silent sound as fallback
            silent = np.zeros((int(self.sample_rate * 0.1), 2), dtype=np.int16)
            buffer = BytesIO()
            wavfile.write(buffer, self.sample_rate, silent)
            buffer.seek(0)
            return pygame.mixer.Sound(buffer)

    def get_audio_description(self, complexity):
        """
        Get a description of what audio features are active.

        Args:
            complexity: Audio complexity setting

        Returns:
            String describing active features
        """
        if complexity == 'simple':
            return "Mono audio with distance-based volume"
        elif complexity == 'moderate':
            return "Stereo panning with distance attenuation"
        else:
            return "Full 3D audio: stereo panning, depth filtering, reverb, distance attenuation"

    def create_warning_tone(self, warning_type, duration=2.0, pulse_rate=4.0):
        """
        Create a pulsating warning tone for space weather alerts.

        Args:
            warning_type: Type of warning ('flare', 'cme', 'storm')
            duration: Total duration in seconds (default 2.0s)
            pulse_rate: Pulses per second (default 4.0 Hz)

        Returns:
            pygame.mixer.Sound object ready for playback
        """
        # Base frequencies for different warning types
        warning_frequencies = {
            'flare': 220.0,     # Solar flare: A3 (low, urgent)
            'cme': 330.0,       # CME: E4 (mid-range)
            'storm': 165.0      # Geomagnetic storm: E3 (deep)
        }

        base_freq = warning_frequencies.get(warning_type, 220.0)

        # Generate time array
        t = np.linspace(0, duration, int(self.sample_rate * duration), False)

        # Create pulsating effect with amplitude modulation
        carrier = np.sin(base_freq * t * 2 * np.pi)
        modulator = (np.sin(pulse_rate * t * 2 * np.pi) + 1) / 2  # 0 to 1 range
        audio_mono = carrier * modulator * 0.3  # Reduce volume to 30%

        # Apply fade-in and fade-out to prevent clicks
        fade_samples = int(self.sample_rate * 0.05)  # 50ms fade
        fade_in = np.linspace(0, 1, fade_samples)
        fade_out = np.linspace(1, 0, fade_samples)
        audio_mono[:fade_samples] *= fade_in
        audio_mono[-fade_samples:] *= fade_out

        # Convert to stereo (same in both channels for warning tones)
        audio_stereo = np.column_stack((audio_mono, audio_mono))

        # Normalize and convert to 16-bit PCM
        max_val = np.max(np.abs(audio_stereo))
        if max_val > 0:
            audio_stereo = audio_stereo / max_val * 0.5  # Keep at 50% max volume

        audio_int16 = (audio_stereo * (2**15 - 1)).astype(np.int16)

        # Create pygame Sound object
        sound_buffer = BytesIO()
        wavfile.write(sound_buffer, self.sample_rate, audio_int16)
        sound_buffer.seek(0)

        try:
            sound = pygame.mixer.Sound(sound_buffer)
            return sound
        except Exception as e:
            logging.error(f"Failed to create warning sound: {e}")
            # Return silent sound as fallback
            silent = np.zeros((int(self.sample_rate * 0.1), 2), dtype=np.int16)
            buffer = BytesIO()
            wavfile.write(buffer, self.sample_rate, silent)
            buffer.seek(0)
            return pygame.mixer.Sound(buffer)
