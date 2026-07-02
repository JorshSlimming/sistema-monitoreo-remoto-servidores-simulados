import socket
import threading

from server.client_session import ClientSession
from server.command_dispatcher import CommandDispatcher
from server.server_config import ServerConfig
from server.server_state import ServerState


class ConnectionManager:
    def __init__(
        self,
        config: ServerConfig,
        state: ServerState,
        dispatcher: CommandDispatcher,
    ) -> None:
        self.config = config
        self.state = state
        self.dispatcher = dispatcher
        self._threads: list[threading.Thread] = []

    def serve_forever(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.config.host, self.config.port))
            server_socket.listen()
            print(f"[server] listening on {self.config.host}:{self.config.port}")

            try:
                while True:
                    conn, address = server_socket.accept()
                    session = ClientSession(
                        conn=conn,
                        address=address,
                        config=self.config,
                        state=self.state,
                        dispatcher=self.dispatcher,
                    )
                    thread = threading.Thread(target=session.run, daemon=True)
                    thread.start()
                    self._threads.append(thread)
            except KeyboardInterrupt:
                print("\n[server] shutdown requested")
