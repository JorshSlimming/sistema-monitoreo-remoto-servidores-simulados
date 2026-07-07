import time
import unittest

from server.server_state import ServerState


class ServerStateTests(unittest.TestCase):
    def test_confirm_unknown_command_returns_false(self) -> None:
        state = ServerState()

        self.assertFalse(state.confirm_command(999))

    def test_expired_command_is_pruned_and_not_pending(self) -> None:
        state = ServerState()
        state.register_command(1, "restart_service", "node-01")
        state.sent_commands[1].timestamp = time.time() - state.command_timeout - 1

        self.assertFalse(state.is_action_pending("restart_service", "node-01"))
        self.assertEqual(state.sent_commands[1].status, "timed_out")


if __name__ == "__main__":
    unittest.main()
