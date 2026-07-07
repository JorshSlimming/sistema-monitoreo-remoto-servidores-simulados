# Diagrama de arquitectura

```mermaid
flowchart TB
    subgraph Clientes["Clientes TCP"]
        N1["node-01<br/>client/tcp_client.py"]
        N2["node-02<br/>client/tcp_client.py"]
        N3["node-03<br/>client/tcp_client.py"]
    end

    subgraph ServidorTCP["Servidor Central TCP"]
        CM["ConnectionManager<br/>server/connection_manager.py"]
        CS["ClientSession (por hilo)<br/>server/client_session.py"]
        SS["ServerState (cooldown)<br/>server/server_state.py"]
        CD["CommandDispatcher<br/>server/command_dispatcher.py"]
        SC["ServerConfig<br/>server/server_config.py"]
    end

    subgraph Shared["Capa Compartida"]
        AUTH["Auth<br/>shared/auth.py"]
        SEC["Secure Channel<br/>shared/secure_channel.py"]
    end

    subgraph Persistencia["Persistencia"]
        DB["DatabaseStore<br/>storage/store.py"]
        SQLITE[("SQLite<br/>data/monitor.db")]
    end

    subgraph Frontend["Frontend Web"]
        DASH["Dashboard Server<br/>frontend/dashboard_server.py"]
        API["/api/state (SSOT)"]
        STATIC["static/app.js + style.css"]
        BROWSER["Navegador (poll 1s)"]
    end

    N1 -- "TCP / PSK + secure frames" --> CM
    N2 -- "TCP / PSK + secure frames" --> CM
    N3 -- "TCP / PSK + secure frames" --> CM

    CM -- "acepta conexión" --> CS
    CS -- "PSK/token por nodo" --> AUTH
    CS -- "handshake + cifrado" --> SEC
    CS -- "actualiza estado (cooldown)" --> SS
    CS -- "detecta anomalía" --> CD
    CD -- "command" --> CS
    CS -- "persiste métrica" --> DB
    CS -- "persiste comando" --> DB
    CS -- "persiste ACK" --> DB
    DB --> SQLITE
    CS -- "metric normal?" --> N1
    CS -- "command (reduce_cpu)" --> N1
    N1 -- "ack (enriquecido)" --> CS

    SQLITE -. "lectura" .-> DASH
    DASH --> API
    API -. "HTTP JSON" .-> BROWSER
    STATIC -. "sirve" .-> DASH
    BROWSER -. "solicita /api/state" .-> API

    style N1 fill:#d4f1f9
    style N2 fill:#d4f1f9
    style N3 fill:#d4f1f9
    style CM fill:#d5e8d4
    style CS fill:#d5e8d4
    style SS fill:#d5e8d4
    style CD fill:#d5e8d4
    style SC fill:#d5e8d4
    style AUTH fill:#ffe6cc
    style SEC fill:#ffe6cc
    style DB fill:#e1d5e7
    style SQLITE fill:#e1d5e7
    style DASH fill:#fff2cc
    style API fill:#fff2cc
    style STATIC fill:#fff2cc
    style BROWSER fill:#fff2cc
```

## Flujo de mensajes

```mermaid
sequenceDiagram
    participant C as Cliente (node-01)
    participant S as Servidor TCP
    participant A as Auth
    participant DB as SQLite
    participant F as Frontend /api/state

    C->>S: {"type":"hello","node_id":"node-01"}
    S->>A: busca PSK de node-01
    A-->>S: PSK valida
    S->>C: {"type":"challenge","nonce":"..."}
    C->>S: {"type":"challenge_response","proof":"..."}
    S->>C: {"type":"ready"}
    C->>S: secure(metric: cpu=95, mitigation_active=true, ...)
    S->>DB: INSERT metric
    S->>C: secure(command: reduce_cpu)
    S->>DB: INSERT command
    C->>C: aplica comando y reduce CPU gradualmente
    C->>S: secure(ack: command_id=1, applied)
    S->>DB: INSERT ack
    C->>S: secure(metric: cpu=40, mitigation_active=false)
    S->>DB: INSERT metric
    F->>DB: SELECT cada 1s
    F-->>F: construye /api/state
    F-->>C: poll cada 1s (navegador)
```

## Flujo de reconexión

```mermaid
sequenceDiagram
    participant C as Cliente
    participant S as Servidor

    C->>S: TCP connect
    S-->>C: SYN-ACK
    C->>S: metric
    Note over C,S: conexión activa
    S--xS: servidor cae
    C->>C: detecta ConnectionRefusedError
    C->>C: espera 5s
    C->>S: TCP reconnect
    S-->>C: SYN-ACK
    C->>S: metric (seq continúa)
```

## Componentes del frontend

```
┌──────────────────────────────────────────┐
│  Navegador Web                           │
│  ┌────────────────────────────────────┐  │
│  │  Dashboard HTML (index.html)        │  │
│  │  ┌──────────────┐ ┌─────────────┐  │  │
│  │  │ Panel nodos  │ │ Gráfico     │  │  │
│  │  │ (tabla)      │ │ (CPU/RAM/   │  │  │
│  │  │              │ │  latencia)  │  │  │
│  │  └──────────────┘ └─────────────┘  │  │
│  │  ┌──────────────┐ ┌─────────────┐  │  │
│  │  │ Eventos      │ │ Logs        │  │  │
│  │  │ (comandos +  │ │ (sistema)   │  │  │
│  │  │  ACKs)       │ │             │  │  │
│  │  └──────────────┘ └─────────────┘  │  │
│  │  ┌──────────────────────────────┐  │  │
│  │  │  Controles de escenario      │  │  │
│  │  └──────────────────────────────┘  │  │
│  └────────────────────────────────────┘  │
│  Polling: GET /api/state cada 1000ms     │
└──────────────────────────────────────────┘
```
