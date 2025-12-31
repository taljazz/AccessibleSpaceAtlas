"""
Speech handler for screen reader integration.
Provides asynchronous text-to-speech via Cytolk/Tolk library.
"""
import threading
import queue
import time
import logging

# Attempt to import Cytolk for screen reader support
try:
    from cytolk import tolk
    cytolk_available = True
except ImportError:
    logging.warning("Cytolk not installed. Screen reader support disabled.")
    cytolk_available = False
    tolk = None


class SpeechHandler(threading.Thread):
    """Thread to handle speech asynchronously."""
    def __init__(self, speech_queue: queue.Queue, stop_event: threading.Event):
        super().__init__(daemon=True)
        self.speech_queue = speech_queue
        self.stop_event = stop_event

    def run(self):
        """Main thread loop to handle speech messages."""
        while not self.stop_event.is_set():
            try:
                # Wait for a speech message with a timeout
                message = self.speech_queue.get(timeout=0.1)
                if message:
                    self._speak_message(message)
            except queue.Empty:
                continue  # No message in queue, continue waiting
            except Exception as e:
                logging.error(f"Error in SpeechHandler: {e}")

    def _speak_message(self, message: str):
        """Speak the given message using Tolk."""
        if cytolk_available and tolk:
            try:
                tolk.speak(message)  # Correct method name
                logging.info(f"Spoken: {message}")
            except Exception as e:
                logging.error(f"Failed to speak message '{message}': {e}")
                # Optional: Re-queue the message if necessary
                time.sleep(0.5)  # Avoid flooding in case of repeated errors
        else:
            logging.info(f"Speech skipped (Cytolk not available): {message}")

    def shutdown(self):
        """Stop the speech handler gracefully."""
        self.stop_event.set()  # Signal the thread to stop
        self.join(timeout=1)  # Wait for the thread to finish
