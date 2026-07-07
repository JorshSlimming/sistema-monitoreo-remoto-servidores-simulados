import socket
import threading

from server.client_session import ClientSession
from server.command_dispatcher import CommandDispatcher
from server.server_config import ServerConfig
from server.server_state import ServerState
from storage.store import DatabaseStore


class ConnectionManager:
    def __init__(
        self,
        config: ServerConfig,
        state: ServerState,
        dispatcher: CommandDispatcher,
        store: DatabaseStore | None = None,
    ) -> None:
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
        self.store = store
        self._threads: list[threading.Thread] = []

    def serve_forever(self) -> None:
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.config.host, self.config.port))
        self._server_socket.listen()
        self.port = self._server_socket.getsockname()[1]
        print(f"[server] listening on {self.config.host}:{self.port}")

        try:
            while True:
                conn, address = self._server_socket.accept()
                session = ClientSession(
                    conn=conn,
                    address=address,
                    config=self.config,
                    state=self.state,
                    dispatcher=self.dispatcher,
                    store=self.store,
                )
                thread = threading.Thread(target=session.run, daemon=True)
                thread.start()
                self._threads.append(thread)
        except (KeyboardInterrupt, OSError):
            print("\n[server] shutdown requested")

    def stop(self) -> None:
        """Shut down the server and release the port."""
        if hasattr(self, "_server_socket"):
            self._server_socket.close()
