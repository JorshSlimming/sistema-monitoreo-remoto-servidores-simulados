from server.command_dispatcher import CommandDispatcher
from server.connection_manager import ConnectionManager
from server.server_config import load_server_config
from server.server_state import ServerState


def main() -> None:
    config = load_server_config()
    state = ServerState()
    dispatcher = CommandDispatcher()
    manager = ConnectionManager(config, state, dispatcher)
    manager.serve_forever()


if __name__ == "__main__":
    main()
