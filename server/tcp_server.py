from server.command_dispatcher import CommandDispatcher
from server.connection_manager import ConnectionManager
from server.server_config import load_server_config
from server.server_state import ServerState
from storage.store import DatabaseStore


def main() -> None:
    config = load_server_config()
    store = DatabaseStore(config.db_path)
    state = ServerState()
    dispatcher = CommandDispatcher()
    manager = ConnectionManager(config, state, dispatcher, store=store)
    try:
        manager.serve_forever()
    finally:
        store.close()


if __name__ == "__main__":
    main()
