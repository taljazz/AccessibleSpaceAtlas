"""
Navigation controller for spatial and list-based navigation.
"""


class NavigationController:
    """Manages navigation state and object selection."""

    def __init__(self):
        self.navigation_mode = 'spatial'  # 'spatial' or 'jump'
        self.selected_index = 0
        self.jump_mode_index = 0

    def enter_jump_mode(self):
        """Enter jump/list mode navigation."""
        self.navigation_mode = 'jump'
        self.jump_mode_index = 0

    def exit_jump_mode(self, selected_index):
        """Exit jump mode and return to spatial navigation."""
        self.navigation_mode = 'spatial'
        self.selected_index = selected_index

    def is_jump_mode(self):
        """Check if currently in jump mode."""
        return self.navigation_mode == 'jump'

    def get_next_spatial_object(self, celestial_objects, current_index, direction):
        """
        Find the index of the next celestial object based on the given direction.

        Parameters:
        - celestial_objects: List of CelestialObject instances.
        - current_index: Current selected object's index.
        - direction: 'left', 'right', 'up', 'down'.

        Returns:
        - Index of the next celestial object.
        """
        if current_index is None or current_index < 0 or current_index >= len(celestial_objects):
            return None

        current_obj = celestial_objects[current_index]
        candidates = []

        for idx, obj in enumerate(celestial_objects):
            if direction == 'left' and obj.screen_pos[0] < current_obj.screen_pos[0]:
                candidates.append((idx, obj))
            elif direction == 'right' and obj.screen_pos[0] > current_obj.screen_pos[0]:
                candidates.append((idx, obj))
            elif direction == 'up' and obj.screen_pos[1] < current_obj.screen_pos[1]:
                candidates.append((idx, obj))
            elif direction == 'down' and obj.screen_pos[1] > current_obj.screen_pos[1]:
                candidates.append((idx, obj))

        if not candidates:
            return current_index  # No movement

        if direction in ['left', 'right']:
            # Sort candidates based on x-coordinate
            if direction == 'left':
                # Closest to current x, i.e., largest x < current x
                candidates.sort(key=lambda x: x[1].screen_pos[0], reverse=True)
            else:
                # 'right' - smallest x > current x
                candidates.sort(key=lambda x: x[1].screen_pos[0])
            return candidates[0][0]
        elif direction in ['up', 'down']:
            # Sort candidates based on y-coordinate
            if direction == 'up':
                # Closest to current y, i.e., largest y < current y
                candidates.sort(key=lambda x: x[1].screen_pos[1], reverse=True)
            else:
                # 'down' - smallest y > current y
                candidates.sort(key=lambda x: x[1].screen_pos[1])
            return candidates[0][0]
        else:
            return current_index
