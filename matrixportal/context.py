# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Application context for sharing resources across modules."""


class AppContext:
    """Container for shared application resources.

    This provides a clean way to pass dependencies to route handlers
    and other modules without relying on global variables.
    """

    def __init__(self, display_manager, requests_session, api_key):
        """Initialize application context.

        Args:
            display_manager: DisplayManager instance for controlling the display
            requests_session: adafruit_requests.Session for HTTP requests
            api_key: API key for authentication (from settings.toml)
        """
        self.display = display_manager
        self.requests = requests_session
        self.api_key = api_key
