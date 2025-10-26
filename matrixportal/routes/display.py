# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Route handler for /display endpoint (binary bitmap upload)."""

import gc
import utils
from adafruit_httpserver import Request, Response


def register(server, context):
    """Register the /display route with the server.

    Args:
        server: adafruit_httpserver.Server instance
        context: AppContext with shared resources
    """

    @server.route("/display", methods=["POST"])
    def display_bitmap_handler(request: Request):
        """Handle POST requests with bitmap data in body (raw binary)"""
        # Aggressive GC before handling request
        gc.collect()
        print(f"Memory at request start: {gc.mem_free()} bytes free")
        print("\nReceived POST request to /display")

        try:
            # Get raw binary data from POST body
            bmp_data = request.body

            if not bmp_data or len(bmp_data) < 138:
                print(f"Invalid or empty bitmap data (size: {len(bmp_data) if bmp_data else 0})")
                return Response(request, "Invalid bitmap data", status=(400, "Bad Request"))

            print(f"Received {len(bmp_data)} bytes of bitmap data")

            # Parse bitmap directly from bytes
            bmp = utils.bitmap_from_bytes(bmp_data, source_name="uploaded")

            # Free bitmap data immediately
            del bmp_data
            gc.collect()

            # Display the bitmap (clears old display and creates TileGrid)
            context.display.display_bitmap(bmp)

            print("Displayed uploaded bitmap")

            return Response(request, "Bitmap displayed successfully", status=(200, "OK"))

        except Exception as e:
            print(f"Error loading bitmap: {e}")
            return Response(request, f"Error loading bitmap: {e}", status=(500, "Internal Server Error"))
