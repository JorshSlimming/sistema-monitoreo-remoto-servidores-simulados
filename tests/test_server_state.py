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

    def test_pending_blocks_duplicate(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        self.assertTrue(state.is_action_pending("reduce_cpu", "node-01"))

    def test_different_node_not_blocked(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        self.assertFalse(state.is_action_pending("reduce_cpu", "node-02"))

    def test_different_action_not_blocked(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        self.assertFalse(state.is_action_pending("reduce_ram", "node-01"))

    def test_confirmed_within_cooldown_blocks_duplicate(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        state.confirm_command(1)
        # Should still block within cooldown window
        self.assertTrue(state.is_action_pending("reduce_cpu", "node-01"))

    def test_confirmed_after_cooldown_allows_new(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        state.confirm_command(1)
        # Manually age the command past the cooldown
        state.sent_commands[1].timestamp = time.time() - state.cooldown_seconds - 1
        self.assertFalse(state.is_action_pending("reduce_cpu", "node-01"))

    def test_cleanup_expired_removes_old_commands(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        state.register_command(2, "reduce_ram", "node-01")
        state.sent_commands[1].timestamp = time.time() - 120
        state.sent_commands[2].timestamp = time.time() - 120
        removed = state.cleanup_expired(max_age=60)
        self.assertEqual(removed, 2)
        self.assertEqual(len(state.sent_commands), 0)

    def test_cleanup_expired_keeps_recent_commands(self) -> None:
        state = ServerState()
        state.register_command(1, "reduce_cpu", "node-01")
        removed = state.cleanup_expired(max_age=60)
        self.assertEqual(removed, 0)
        self.assertIn(1, state.sent_commands)


if __name__ == "__main__":
    unittest.main()
