"""
NASA DONKI Space Weather API Client.
Fetches real-time solar flare alerts, CME, and other space weather events.
"""
import requests
import logging
from datetime import datetime, timedelta


class SpaceWeatherClient:
    """Client for NASA DONKI (Database Of Notifications, Knowledge, Information) API."""

    def __init__(self, api_key="DEMO_KEY"):
        """
        Initialize the space weather client.

        Args:
            api_key: NASA API key (default uses DEMO_KEY with rate limits)
                    Get your free key at: https://api.nasa.gov/
        """
        self.base_url = "https://api.nasa.gov/DONKI"
        self.api_key = api_key

    def get_solar_flares(self, days_back=7, most_recent=False):
        """
        Get recent solar flare events.

        Args:
            days_back: Number of days to look back (default 7)
            most_recent: If True, use mostRecent parameter for efficiency (default False)

        Returns:
            List of solar flare events
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "api_key": self.api_key
        }

        # Add mostRecent parameter for real-time efficiency (2025 API feature)
        if most_recent:
            params["mostRecent"] = "true"

        try:
            response = requests.get(f"{self.base_url}/FLR", params=params, timeout=10)
            response.raise_for_status()
            flares = response.json()
            logging.info(f"Fetched {len(flares)} solar flare events")
            return flares
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch solar flares: {e}")
            return []

    def get_cme_events(self, days_back=7, most_recent=False):
        """
        Get recent Coronal Mass Ejection (CME) events.

        Args:
            days_back: Number of days to look back (default 7)
            most_recent: If True, use mostRecent parameter for efficiency (default False)

        Returns:
            List of CME events
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "api_key": self.api_key
        }

        # Add mostRecent parameter for real-time efficiency (2025 API feature)
        if most_recent:
            params["mostRecent"] = "true"

        try:
            response = requests.get(f"{self.base_url}/CME", params=params, timeout=10)
            response.raise_for_status()
            cme_events = response.json()
            logging.info(f"Fetched {len(cme_events)} CME events")
            return cme_events
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch CME events: {e}")
            return []

    def get_geomagnetic_storms(self, days_back=7, most_recent=False):
        """
        Get recent geomagnetic storm events.

        Args:
            days_back: Number of days to look back (default 7)
            most_recent: If True, use mostRecent parameter for efficiency (default False)

        Returns:
            List of geomagnetic storm events
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        params = {
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "api_key": self.api_key
        }

        # Add mostRecent parameter for real-time efficiency (2025 API feature)
        if most_recent:
            params["mostRecent"] = "true"

        try:
            response = requests.get(f"{self.base_url}/GST", params=params, timeout=10)
            response.raise_for_status()
            storms = response.json()
            logging.info(f"Fetched {len(storms)} geomagnetic storm events")
            return storms
        except requests.exceptions.RequestException as e:
            logging.error(f"Failed to fetch geomagnetic storms: {e}")
            return []

    def get_space_weather_summary(self, days_back=7):
        """
        Get a summary of all space weather events.

        Args:
            days_back: Number of days to look back (default 7)

        Returns:
            Dictionary with counts and recent events
        """
        flares = self.get_solar_flares(days_back)
        cme_events = self.get_cme_events(days_back)
        storms = self.get_geomagnetic_storms(days_back)

        # Filter for significant events
        significant_flares = [f for f in flares if f.get('classType', '').startswith(('M', 'X'))]

        summary = {
            'flares_total': len(flares),
            'flares_significant': len(significant_flares),
            'cme_events': len(cme_events),
            'geomagnetic_storms': len(storms),
            'recent_flares': flares[:3] if flares else [],
            'recent_cme': cme_events[:3] if cme_events else [],
            'recent_storms': storms[:3] if storms else []
        }

        return summary

    def format_flare_announcement(self, flare):
        """
        Format a solar flare event for screen reader announcement.

        Args:
            flare: Flare event dictionary

        Returns:
            Human-readable announcement string
        """
        class_type = flare.get('classType', 'Unknown')
        begin_time = flare.get('beginTime', 'Unknown time')

        # Parse time if available
        try:
            dt = datetime.fromisoformat(begin_time.replace('Z', '+00:00'))
            time_str = dt.strftime("%B %d at %H:%M UTC")
        except:
            time_str = begin_time

        return f"Solar flare detected: Class {class_type} on {time_str}"

    def format_cme_announcement(self, cme):
        """
        Format a CME event for screen reader announcement.

        Args:
            cme: CME event dictionary

        Returns:
            Human-readable announcement string
        """
        activity_time = cme.get('activityTime', 'Unknown time')

        # Parse time if available
        try:
            dt = datetime.fromisoformat(activity_time.replace('Z', '+00:00'))
            time_str = dt.strftime("%B %d at %H:%M UTC")
        except:
            time_str = activity_time

        return f"Coronal Mass Ejection detected on {time_str}"

    def get_active_warnings(self):
        """
        Get currently active space weather warnings (within last 24 hours).
        Uses mostRecent parameter for efficient real-time alerts.

        Returns:
            List of warning strings for announcements
        """
        warnings = []

        # Check for recent significant solar flares (last 24 hours)
        # Use mostRecent=True for real-time efficiency
        flares = self.get_solar_flares(days_back=1, most_recent=True)
        significant_flares = [f for f in flares if f.get('classType', '').startswith(('M', 'X'))]

        for flare in significant_flares[:2]:  # Limit to 2 most recent
            warnings.append(self.format_flare_announcement(flare))

        # Check for recent CME events
        cme_events = self.get_cme_events(days_back=1, most_recent=True)
        for cme in cme_events[:1]:  # Limit to 1 most recent
            warnings.append(self.format_cme_announcement(cme))

        # Check for geomagnetic storms
        storms = self.get_geomagnetic_storms(days_back=1, most_recent=True)
        if storms:
            storm = storms[0]
            kp_index = storm.get('allKpIndex', [{}])[0].get('kpIndex', 'Unknown')
            warnings.append(f"Geomagnetic storm activity detected. Kp index: {kp_index}")

        return warnings
