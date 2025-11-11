# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Display management for MatrixPortal bitmap display."""

import gc
import displayio
import utils


class DisplayManager:
    """Manages the RGB matrix display and bitmap rendering."""

    def __init__(self, matrix, color_converter):
        """Initialize display manager.

        Args:
            matrix: Matrix object from adafruit_matrixportal.matrix
            color_converter: displayio.ColorConverter for RGB565
        """
        self.splash = displayio.Group()
        self.matrix = matrix
        self.matrix.display.root_group = self.splash
        self.color_converter = color_converter
        self.current_face = None

    def clear_display(self):
        """Clear the display by removing all TileGrids."""
        while len(self.splash) > 0:
            self.splash.pop()

        if self.current_face is not None:
            del self.current_face
            self.current_face = None

        gc.collect()
        print(f"Memory after clearing display: {gc.mem_free()} bytes free")

    def display_bitmap(self, bmp):
        """Clear old display and show new bitmap.

        Args:
            bmp: displayio.Bitmap object to display
        """
        # CRITICAL: Clear old display FIRST, before creating new TileGrid
        # This ensures we never have both bitmaps in RAM at once
        while len(self.splash) > 0:
            self.splash.pop()

        if self.current_face is not None:
            del self.current_face
            self.current_face = None

        # Run garbage collection to free old bitmap/TileGrid
        gc.collect()
        print(f"Memory after clearing old bitmap: {gc.mem_free()} bytes free")

        # Create TileGrid
        new_face = displayio.TileGrid(bmp, pixel_shader=self.color_converter)

        # Delete bitmap reference (TileGrid holds its own reference)
        del bmp
        gc.collect()

        # Update display
        self.splash.append(new_face)
        self.current_face = new_face

        print(f"Memory after displaying bitmap: {gc.mem_free()} bytes free")
        gc.collect()

    def load_and_display_bitmap(self, bitmap_url, requests_session):
        """Fetch and display a bitmap from the given URL.

        Args:
            bitmap_url: URL string to fetch bitmap from
            requests_session: adafruit_requests.Session for HTTP requests
        """
        gc.collect()
        print(f"Memory before load: {gc.mem_free()} bytes free")
        print(f"Fetching bitmap: {bitmap_url}")

        # Start HTTP request
        r = requests_session.get(bitmap_url)

        # Get content length from headers (pre-allocate exact size)
        content_length = int(r.headers.get('content-length', 0))
        print(f"Content-Length: {content_length} bytes")

        if content_length == 0:
            r.close()
            raise ValueError("No Content-Length header in response")

        # Pre-allocate buffer of exact size (ONE allocation, no fragmentation!)
        print(f"Pre-allocating {content_length} byte buffer...")
        bmp_data = bytearray(content_length)

        # Stream directly into pre-allocated buffer
        offset = 0
        for chunk in r.iter_content(chunk_size=1024):  # Use 1KB chunks
            chunk_len = len(chunk)
            bmp_data[offset:offset+chunk_len] = chunk
            offset += chunk_len

        print(f"Downloaded {offset} bytes")
        r.close()

        # Convert to bytes for utils.bitmap_from_bytes()
        bmp_data = bytes(bmp_data)

        del r
        gc.collect()

        # Parse bitmap
        bmp = utils.bitmap_from_bytes(bmp_data, source_name=bitmap_url)

        # Delete bitmap data immediately after parsing
        del bmp_data
        gc.collect()

        # Display the bitmap (clears old display and creates TileGrid)
        self.display_bitmap(bmp)

        print(f"Displayed bitmap: {bitmap_url}")
