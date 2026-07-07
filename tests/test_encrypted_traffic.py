#!/usr/bin/env python3
"""
Integration test for encrypted traffic
"""

import sys
import subprocess
import time
import threading

sys.path.insert(0, '/home/maxi/codigo/sistema-monitoreo-remoto-servidores-simulados')


def run_server():
    """Run server in a separate thread"""
    import socket
    from server.connection_manager import ConnectionManager
    from server.server_config import load_server_config
    from server.server_state import ServerState
    from server.command_dispatcher import CommandDispatcher
    
    config = load_server_config()
    state = ServerState()
    dispatcher = CommandDispatcher()
    manager = ConnectionManager(config, state, dispatcher)
    manager.serve_forever()


def run_client(node_id: str, mode: str):
    """Run client in subprocess"""
    cmd = [
        "python3", "tests/fake_client.py",
        "--node-id", node_id,
        "--mode", mode
    ]
    result = subprocess.run(cmd, cwd="/home/maxi/codigo/sistema-monitoreo-remoto-servidores-simulados")
    return result.returncode == 0


def main():
    print("=" * 60)
    print("Encrypted Traffic Integration Test")
    print("=" * 60)
    
    # Start server in background thread
    print("\n[test] Starting server...")
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    # Test multiple nodes with different modes
    test_cases = [
        ("node-01", "normal", "Normal operation"),
        ("node-02", "high-cpu", "High CPU alert"),
        ("node-03", "high-ram", "High RAM alert"),
        ("node-01", "service-failure", "Service failure alert"),
    ]
    
    passed = 0
    failed = 0
    
    for node_id, mode, description in test_cases:
        print(f"\n[test] {description} ({node_id}, {mode})...")
        try:
            if run_client(node_id, mode):
                print(f"[test] ✓ {description} passed")
                passed += 1
            else:
                print(f"[test] ✗ {description} failed")
                failed += 1
        except Exception as e:
            print(f"[test] ✗ {description} error: {e}")
            failed += 1
        time.sleep(0.5)
    
    print("\n" + "=" * 60)
    print(f"Test Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
