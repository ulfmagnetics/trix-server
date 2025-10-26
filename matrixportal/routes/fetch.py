# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Route handler for /fetch endpoint (URL-based bitmap fetching)."""

import gc
from adafruit_httpserver import Request, Response


def register(server, context):
    """Register the /fetch route with the server.

    Args:
        server: adafruit_httpserver.Server instance
        context: AppContext with shared resources
    """

    @server.route("/fetch", methods=["POST"])
    def fetch_bitmap_handler(request: Request):
        """Handle POST requests with bitmap URL in body"""
        # Aggressive GC before handling request
        gc.collect()
        print(f"Memory at request start: {gc.mem_free()} bytes free")
        print("\nReceived POST request to /fetch")

        try:
            # Extract URL from raw POST body
            body_bytes = request.body
            bitmap_url = body_bytes.decode('utf-8', 'ignore').strip()

            # Immediately free body reference
            del body_bytes
            gc.collect()

            if not bitmap_url:
                print("Empty URL in POST body")
                return Response(request, "Empty URL in POST body", status=(400, "Bad Request"))

            print(f"Received URL: {bitmap_url}")

            # Load and display the bitmap
            context.display.load_and_display_bitmap(bitmap_url, context.requests)

            print("Bitmap loaded and displayed successfully")
            return Response(request, "Bitmap displayed successfully", status=(200, "OK"))

        except Exception as e:
            print(f"Error loading bitmap: {e}")
            return Response(request, f"Error loading bitmap: {e}", status=(500, "Internal Server Error"))
