# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Route handler for /clear endpoint to clear the matrix display."""

import gc
import utils
from adafruit_httpserver import Request, Response


def register(server, context):
    """Register the /clear route with the server.

    Args:
        server: adafruit_httpserver.Server instance
        context: AppContext with shared resources
    """

    @server.route("/clear", methods=["GET"])
    def clear_display_handler(request: Request):
        """Handle GET requests to clear the display"""
        try:
            # Clear the display
            context.display.clear_display()

            print("Display cleared successfully")
            return Response(request, "Display cleared successfully", status=(200, "OK"))

        except Exception as e:
            print(f"Error clearing display: {e}")
            return Response(request, f"Error clearing display: {e}", status=(500, "Internal Server Error"))