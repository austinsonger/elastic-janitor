"""
Background thread manager for the FastAPI web dashboard server.
"""
import threading
import time


class WebServerManager:
    """Manages the uvicorn server in a background daemon thread."""

    def __init__(self, es_client, host="127.0.0.1", port=8000):
        self.es_client = es_client
        self.host = host
        self.port = port
        self._thread = None
        self._server = None

    def start(self):
        """Start the web dashboard server in a background thread."""
        import uvicorn
        from . import server as server_module

        # Inject the ES client into the server module
        server_module.es = self.es_client

        config = uvicorn.Config(
            app="janitor.web.server:app",
            host=self.host,
            port=self.port,
            log_level="warning",
        )
        self._server = uvicorn.Server(config)

        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        # Wait briefly for server to start
        for _ in range(20):
            if self._server.started:
                break
            time.sleep(0.25)

    def stop(self):
        """Signal the server to shut down."""
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
            self._server = None

    def is_running(self):
        """Check if the server thread is alive."""
        return self._thread is not None and self._thread.is_alive()
