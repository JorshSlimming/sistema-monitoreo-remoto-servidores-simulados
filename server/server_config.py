import json
import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    encoding: str = "utf-8"
    message_separator: str = "\n"
    max_line_bytes: int = 8192
    db_path: str = "data/monitor.db"


def load_server_config(path: str | Path | None = None) -> ServerConfig:
    config_path = Path(path or os.getenv("SERVER_CONFIG", "configs/server_config.json"))
    data = {}
    if config_path.exists():
        with config_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

    host = os.getenv("SERVER_HOST", data.get("host", ServerConfig.host))
    port = int(os.getenv("SERVER_PORT", data.get("port", ServerConfig.port)))

    return ServerConfig(
        host=host,
        port=port,
        encoding=data.get("encoding", "utf-8"),
        message_separator=data.get("message_separator", "\n"),
        max_line_bytes=int(data.get("max_line_bytes", 8192)),
        db_path=data.get("db_path", ServerConfig.db_path),
    )
