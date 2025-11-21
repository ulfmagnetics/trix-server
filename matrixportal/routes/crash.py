# SPDX-FileCopyrightText: 2025
# SPDX-License-Identifier: MIT

"""Route handler for /crash endpoint (crash log retrieval)."""

import gc
from adafruit_httpserver import Request, Response
from crash_logger import logger


def register(server, context):
    """Register the /crash route with the server.

    Args:
        server: adafruit_httpserver.Server instance
        context: AppContext with shared resources
    """

    @server.route("/crash", methods=["GET"])
    def crash_log_handler(request: Request):
        """Handle GET requests for crash log retrieval.

        Query parameters:
        - lines: Number of lines to return (default: all)
        - clear: If "true", clear the log after reading
        """
        gc.collect()
        print("\nReceived GET request to /crash")

        try:
            # Parse query parameters
            query_params = {}
            if hasattr(request, 'query_params') and request.query_params:
                query_params = request.query_params

            # Get number of lines (if specified)
            max_lines = None
            if 'lines' in query_params:
                try:
                    max_lines = int(query_params['lines'])
                except ValueError:
                    return Response(request, "Invalid 'lines' parameter", status=(400, "Bad Request"))

            # Read log contents
            log_contents = logger.get_log_contents(max_lines=max_lines)

            # Check if clear requested
            if query_params.get('clear') == 'true':
                logger.clear_log()
                logger.reset_crash_counter()
                log_contents += "\n\n[Log cleared and crash counter reset]"

            return Response(request, log_contents, content_type="text/plain")

        except Exception as e:
            print(f"Error retrieving crash log: {e}")
            logger.log_exception(e, "Crash log retrieval")
            return Response(request, f"Error: {e}", status=(500, "Internal Server Error"))

    @server.route("/crash/counter", methods=["GET"])
    def crash_counter_handler(request: Request):
        """Handle GET requests for crash counter only."""
        gc.collect()
        print("\nReceived GET request to /crash/counter")

        try:
            crash_count = logger.crash_count
            uptime = logger._get_uptime()
            free_mem = gc.mem_free()

            response_text = f"Crash count: {crash_count}\n"
            response_text += f"Uptime: {uptime:.2f}s\n"
            response_text += f"Free memory: {free_mem} bytes\n"

            return Response(request, response_text, content_type="text/plain")

        except Exception as e:
            print(f"Error retrieving crash counter: {e}")
            return Response(request, f"Error: {e}", status=(500, "Internal Server Error"))

    @server.route("/crash/reset", methods=["POST"])
    def crash_reset_handler(request: Request):
        """Handle POST requests to reset crash counter."""
        gc.collect()
        print("\nReceived POST request to /crash/reset")

        try:
            logger.reset_crash_counter()
            return Response(request, "Crash counter reset successfully", status=(200, "OK"))

        except Exception as e:
            print(f"Error resetting crash counter: {e}")
            logger.log_exception(e, "Crash counter reset")
            return Response(request, f"Error: {e}", status=(500, "Internal Server Error"))
