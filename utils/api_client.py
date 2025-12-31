"""
NASA Horizons API client.
Fetches celestial object data from JPL Horizons system.
"""
import requests
import logging
import re
import json
import os
from datetime import datetime
from pathlib import Path
from models.celestial_object import CelestialObject


class HorizonsAPIClient:
    """Client for NASA JPL Horizons API."""

    def __init__(self, cache_file="data/celestial_cache.json"):
        self.base_url = "https://ssd.jpl.nasa.gov/api/horizons.api"
        self.cache_file = Path(cache_file)
        self.cache_max_age_hours = 24  # Cache valid for 24 hours

    def _save_to_cache(self, objects_data):
        """
        Save celestial object data to cache file.

        Args:
            objects_data: List of dictionaries with object data
        """
        try:
            # Ensure data directory exists
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)

            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'objects': objects_data
            }

            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, indent=2)

            logging.info(f"Cached {len(objects_data)} objects to {self.cache_file}")
        except Exception as e:
            logging.error(f"Failed to save cache: {e}")

    def _load_from_cache(self):
        """
        Load celestial object data from cache file.

        Returns:
            List of CelestialObject instances, or None if cache unavailable/expired
        """
        try:
            if not self.cache_file.exists():
                logging.info("No cache file found")
                return None

            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)

            # Check cache age
            timestamp = datetime.fromisoformat(cache_data['timestamp'])
            age_hours = (datetime.now() - timestamp).total_seconds() / 3600

            if age_hours > self.cache_max_age_hours:
                logging.info(f"Cache expired ({age_hours:.1f} hours old)")
                return None

            # Convert cached data back to CelestialObject instances
            objects = []
            for obj_data in cache_data['objects']:
                try:
                    obj = CelestialObject(
                        name=obj_data['name'],
                        type_=obj_data['type'],
                        x=obj_data['x'],
                        y=obj_data['y'],
                        z=obj_data['z'],
                        size=obj_data.get('size', 5),
                        distance=obj_data['distance'],
                        vx=obj_data.get('vx', 0.0),
                        vy=obj_data.get('vy', 0.0),
                        vz=obj_data.get('vz', 0.0),
                        parent=obj_data.get('parent'),
                        generate_sound=False
                    )
                    objects.append(obj)
                except Exception as e:
                    logging.error(f"Error loading cached object {obj_data.get('name', 'unknown')}: {e}")

            logging.info(f"Loaded {len(objects)} objects from cache ({age_hours:.1f} hours old)")
            return objects

        except Exception as e:
            logging.error(f"Failed to load cache: {e}")
            return None

    def fetch_celestial_objects(self, object_definitions):
        """
        Fetch data for all celestial objects from the Horizons API.

        Args:
            object_definitions: List of dicts with name, command, type, size

        Returns:
            List of CelestialObject instances
        """
        celestial_objects = []

        for obj in object_definitions:
            # Validate COMMAND format (remove extra quotes if present)
            command = obj["command"].strip("'\"")
            params = {
                "format": "json",
                "COMMAND": f"'{command}'",
                "EPHEM_TYPE": "VECTORS",
                "CENTER": "'@sun'",          # Heliocentric
                "START_TIME": "'2024-12-01'",
                "STOP_TIME": "'2024-12-31'",
                "STEP_SIZE": "'1d'",
                "REF_PLANE": "'ECLIPTIC'",
                "OUT_UNITS": "'AU-D'",
                "VEC_CORR": "'NONE'",
                "VEC_LABELS": "'YES'",
            }

            try:
                response = requests.get(self.base_url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                # Check if 'result' key exists in the response
                if "result" not in data:
                    logging.error(f"No 'result' data found for {obj['name']}. Response: {data}")
                    continue

                # Parse text-based ephemeris data from result field
                result_text = data['result']

                # Extract data between $$SOE and $$EOE markers
                if '$$SOE' not in result_text or '$$EOE' not in result_text:
                    logging.error(f"No ephemeris data markers found for {obj['name']}")
                    continue

                soe_start = result_text.index('$$SOE') + 5
                eoe_end = result_text.index('$$EOE')
                ephemeris_text = result_text[soe_start:eoe_end].strip()

                # Parse the ephemeris lines using more robust regex patterns
                # This handles variations in formatting and is more resilient to API changes
                lines = ephemeris_text.split('\n')
                x, y, z = None, None, None
                vx, vy, vz = None, None, None

                # Improved regex patterns that handle more format variations
                # Matches scientific notation with optional signs and flexible spacing
                coord_pattern = r'[-+]?\d+\.?\d*(?:[Ee][-+]?\d+)?'

                for i, line in enumerate(lines):
                    line = line.strip()

                    # Try to parse position coordinates (X, Y, Z)
                    # More flexible pattern that handles various spacing and formats
                    # Check for lines starting with 'X' (not 'VX') to distinguish position from velocity
                    if (line.startswith('X ') or line.startswith('X=')) and 'Y' in line and 'Z' in line:
                        try:
                            # Extract X, Y, Z values with improved regex
                            x_match = re.search(rf'X\s*=\s*({coord_pattern})', line)
                            y_match = re.search(rf'Y\s*=\s*({coord_pattern})', line)
                            z_match = re.search(rf'Z\s*=\s*({coord_pattern})', line)

                            if x_match and y_match and z_match:
                                x = float(x_match.group(1))
                                y = float(y_match.group(1))
                                z = float(z_match.group(1))
                                logging.debug(f"Parsed position for {obj['name']}: X={x}, Y={y}, Z={z}")
                            else:
                                # Try alternative parsing: split by spaces and look for numeric values
                                parts = line.split()
                                values = []
                                for part in parts:
                                    try:
                                        val = float(part)
                                        values.append(val)
                                    except ValueError:
                                        continue

                                if len(values) >= 3:
                                    x, y, z = values[0], values[1], values[2]
                                else:
                                    logging.warning(f"Could not parse coordinates from line: {line}")
                                    continue
                        except (ValueError, IndexError) as e:
                            logging.error(f"Error parsing coordinates for {obj['name']}: {e}")
                            continue

                    # Try to parse velocity components (VX, VY, VZ)
                    elif 'VX' in line and 'VY' in line and 'VZ' in line:
                        try:
                            # Extract VX, VY, VZ values with improved regex
                            vx_match = re.search(rf'VX\s*=?\s*({coord_pattern})', line)
                            vy_match = re.search(rf'VY\s*=?\s*({coord_pattern})', line)
                            vz_match = re.search(rf'VZ\s*=?\s*({coord_pattern})', line)

                            if vx_match and vy_match and vz_match:
                                vx = float(vx_match.group(1))
                                vy = float(vy_match.group(1))
                                vz = float(vz_match.group(1))

                                # Now we have both position and velocity, create object
                                if x is not None and y is not None and z is not None:
                                    distance = (x**2 + y**2 + z**2) ** 0.5

                                    celestial_objects.append(
                                        CelestialObject(
                                            name=obj["name"],
                                            type_=obj["type"],
                                            x=x,
                                            y=y,
                                            z=z,
                                            size=obj.get("size", 5),
                                            distance=distance,
                                            vx=vx,
                                            vy=vy,
                                            vz=vz,
                                            parent=obj.get("parent"),  # Parent object name
                                            generate_sound=False  # Sound generated by AudioEngine later
                                        )
                                    )
                                    logging.info(f"Loaded {obj['name']}: pos=({x:.3f}, {y:.3f}, {z:.3f}) AU, vel=({vx:.6f}, {vy:.6f}, {vz:.6f}) AU/day, distance={distance:.3f} AU")
                                    break  # Only take first ephemeris point
                            else:
                                # Try alternative parsing
                                parts = line.split()
                                values = []
                                for part in parts:
                                    try:
                                        val = float(part)
                                        values.append(val)
                                    except ValueError:
                                        continue

                                if len(values) >= 3 and x is not None:
                                    vx, vy, vz = values[0], values[1], values[2]
                                    distance = (x**2 + y**2 + z**2) ** 0.5

                                    celestial_objects.append(
                                        CelestialObject(
                                            name=obj["name"],
                                            type_=obj["type"],
                                            x=x,
                                            y=y,
                                            z=z,
                                            size=obj.get("size", 5),
                                            distance=distance,
                                            vx=vx,
                                            vy=vy,
                                            vz=vz,
                                            parent=obj.get("parent"),  # Parent object name
                                            generate_sound=False  # Sound generated by AudioEngine later
                                        )
                                    )
                                    logging.info(f"Loaded {obj['name']}: pos=({x:.3f}, {y:.3f}, {z:.3f}) AU, vel=({vx:.6f}, {vy:.6f}, {vz:.6f}) AU/day, distance={distance:.3f} AU")
                                    break
                                else:
                                    logging.warning(f"Could not parse velocities from line: {line}")
                        except (ValueError, IndexError) as e:
                            logging.error(f"Error parsing velocities for {obj['name']}: {e}")
                            continue
            except requests.exceptions.RequestException as e:
                logging.error(f"Request exception for {obj['name']}: {e}")
            except ValueError as ve:
                logging.error(f"Value error processing data for {obj['name']}: {ve}")
            except Exception as ex:
                logging.error(f"Unexpected error fetching data for {obj['name']}: {ex}")

        # If we got objects, cache them
        if celestial_objects:
            # Convert to cacheable format
            cache_data = []
            for obj in celestial_objects:
                cache_data.append({
                    'name': obj.name,
                    'type': obj.type,
                    'x': obj.x,
                    'y': obj.y,
                    'z': obj.z,
                    'size': obj.size,
                    'distance': obj.distance,
                    'vx': obj.vx,
                    'vy': obj.vy,
                    'vz': obj.vz,
                    'parent': obj.parent
                })
            self._save_to_cache(cache_data)
        else:
            # No objects from API, try cache
            logging.warning("No objects fetched from API, trying cache...")
            cached_objects = self._load_from_cache()
            if cached_objects:
                return cached_objects
            else:
                logging.error("No cached data available. Cannot load celestial objects.")

        return celestial_objects

    def fetch_with_fallback(self, object_definitions):
        """
        Fetch objects from API with cache fallback.
        Tries API first, falls back to cache if API fails.

        Args:
            object_definitions: List of dicts with name, command, type, size

        Returns:
            Tuple of (List of CelestialObject instances, bool indicating if from cache)
        """
        # Try to load from cache first to get immediate results
        cached_objects = self._load_from_cache()

        # Try API
        api_objects = self.fetch_celestial_objects(object_definitions)

        if api_objects:
            return api_objects, False  # Fresh data from API
        elif cached_objects:
            logging.info("Using cached data due to API failure")
            return cached_objects, True  # Cached data
        else:
            return [], False  # No data available
