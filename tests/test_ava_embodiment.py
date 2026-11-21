"""Regression checks for AVA's portable, simulation-only robotics interface."""

import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from ava_core.embodiment import BodyCommand, EmbodimentError, EmbodimentGateway, RobotState, SimulatedBody


def say(request_id="say-1", robot_id="ava-sim"):
    return BodyCommand(request_id=request_id, robot_id=robot_id, kind="say", text="سلام")


def step(request_id="step-1", distance_m=0.1):
    return BodyCommand(request_id=request_id, robot_id="ava-sim", kind="step", distance_m=distance_m)


class EmbodimentTests(unittest.TestCase):
    def setUp(self):
        self.body = SimulatedBody()
        self.audit = []

        def authorize(owner_id, command):
            self.audit.append((owner_id, command.request_id))
            return True

        self.gateway = EmbodimentGateway(owner_id="owner-1", body=self.body, authorize=authorize)

    def test_portable_read_only_state(self):
        state = self.gateway.observe()
        self.assertEqual(state.robot_id, "ava-sim")
        self.assertEqual(state.capabilities, frozenset({"say", "step"}))
        self.assertEqual(state.battery_percent, 100)

    def test_simulated_commands_have_observable_results_and_receipts(self):
        first = self.gateway.simulate(say())
        second = self.gateway.simulate(step())
        self.assertTrue(first.simulated and second.simulated)
        self.assertEqual(self.body.last_speech, "سلام")
        self.assertAlmostEqual(self.body.travelled_m, 0.1)
        self.assertEqual(self.audit, [("owner-1", "say-1"), ("owner-1", "step-1")])

    def test_default_deny_and_explicit_boolean_authorization(self):
        without_authorizer = EmbodimentGateway(owner_id="owner-1", body=self.body)
        with self.assertRaises(PermissionError):
            without_authorizer.simulate(say())
        untrusted = EmbodimentGateway(owner_id="owner-1", body=self.body, authorize=lambda *_: 1)
        with self.assertRaises(PermissionError):
            untrusted.simulate(say())
        self.assertEqual(self.body.last_speech, "")

    def test_replay_blocked_before_second_movement(self):
        self.gateway.simulate(step())
        with self.assertRaisesRegex(EmbodimentError, "replayed"):
            self.gateway.simulate(step())
        self.assertAlmostEqual(self.body.travelled_m, 0.1)

    def test_replay_blocked_across_two_gateway_objects(self):
        self.gateway.simulate(step())
        another = EmbodimentGateway(owner_id="owner-1", body=self.body, authorize=lambda *_: True)
        with self.assertRaisesRegex(EmbodimentError, "replayed"):
            another.simulate(step())
        self.assertAlmostEqual(self.body.travelled_m, 0.1)

    def test_wrong_robot_disconnected_and_emergency_stop_blocked(self):
        with self.assertRaisesRegex(EmbodimentError, "another robot"):
            self.gateway.simulate(say(robot_id="different"))
        self.body.connected = False
        with self.assertRaises(EmbodimentError):
            self.gateway.simulate(say())
        self.body.connected = True
        self.body.emergency_stop = True
        with self.assertRaises(EmbodimentError):
            self.gateway.simulate(step())

    def test_low_battery_blocks_movement_not_speech(self):
        self.body.battery_percent = 19
        with self.assertRaisesRegex(EmbodimentError, "battery"):
            self.gateway.simulate(step())
        self.assertTrue(self.gateway.simulate(say()).simulated)

    def test_unbounded_or_malformed_commands_rejected(self):
        bad = [
            dict(request_id="", robot_id="ava-sim", kind="say", text="hi"),
            dict(request_id="a", robot_id="ava-sim", kind="jump"),
            dict(request_id="a", robot_id="ava-sim", kind="say", text=" "),
            dict(request_id="a", robot_id="ava-sim", kind="say", text="x" * 301),
            dict(request_id="a", robot_id="ava-sim", kind="say", text="hi", distance_m=0.1),
            dict(request_id="a", robot_id="ava-sim", kind="step", distance_m=1),
            dict(request_id="a", robot_id="ava-sim", kind="step", distance_m=float("nan")),
            dict(request_id="a", robot_id="ava-sim", kind="step", distance_m=True),
            dict(request_id="a", robot_id="ava-sim", kind="step", text="hi", distance_m=0.1),
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(ValueError):
                BodyCommand(**data)

    def test_physical_adapter_is_read_only_even_when_authorized(self):
        class HardwareAdapter:
            def observe(self):
                return RobotState("ava-sim", datetime.now(timezone.utc), True, False, 100,
                                  frozenset({"say", "step"}))

            def _apply(self, command):
                raise AssertionError("physical device must never be invoked")

        gateway = EmbodimentGateway(owner_id="owner-1", body=HardwareAdapter(), authorize=lambda *_: True)
        self.assertEqual(gateway.observe().robot_id, "ava-sim")
        with self.assertRaisesRegex(EmbodimentError, "physical actuation"):
            gateway.simulate(say())

    def test_bad_vendor_status_rejected(self):
        class BadAdapter:
            def observe(self):
                return replace(SimulatedBody().observe(), observed_at=datetime.now())

        gateway = EmbodimentGateway(owner_id="owner-1", body=BadAdapter())
        with self.assertRaisesRegex(EmbodimentError, "timezone"):
            gateway.observe()

    def test_stale_and_future_dated_telemetry_block_actions(self):
        original = self.body.observe()
        for observed_at in (
            datetime.now(timezone.utc) - timedelta(seconds=60),
            datetime.now(timezone.utc) + timedelta(seconds=60),
        ):
            self.body.observe = lambda at=observed_at: replace(original, observed_at=at)
            with self.subTest(observed_at=observed_at), self.assertRaisesRegex(EmbodimentError, "stale"):
                self.gateway.simulate(step())

    def test_claimed_unsupported_capability_is_rejected(self):
        original = self.body.observe()
        self.body.observe = lambda: replace(original, capabilities=frozenset({"say"}))
        with self.assertRaisesRegex(EmbodimentError, "capability"):
            self.gateway.simulate(step())

    def test_invalid_battery_telemetry_is_rejected(self):
        self.body.battery_percent = 120
        with self.assertRaisesRegex(EmbodimentError, "battery"):
            self.gateway.observe()

    def test_simulator_subclass_cannot_escape_hardware_guard(self):
        class DangerousSubclass(SimulatedBody):
            def _apply(self, command):
                raise AssertionError("subclass must never actuate")

        gateway = EmbodimentGateway(owner_id="owner-1", body=DangerousSubclass(), authorize=lambda *_: True)
        with self.assertRaisesRegex(EmbodimentError, "physical actuation"):
            gateway.simulate(say())

    def test_rejected_permission_does_not_consume_command_id(self):
        permission = {"enabled": False}
        gateway = EmbodimentGateway(
            owner_id="owner-1", body=self.body,
            authorize=lambda *_: permission["enabled"],
        )
        with self.assertRaises(PermissionError):
            gateway.simulate(say())
        permission["enabled"] = True
        self.assertTrue(gateway.simulate(say()).simulated)

    def test_validation_of_simulated_battery_and_identity(self):
        for battery in [-1, 101, True, 20.5]:
            with self.subTest(battery=battery), self.assertRaises(ValueError):
                SimulatedBody(battery_percent=battery)
        with self.assertRaises(ValueError):
            SimulatedBody(robot_id=" ")


if __name__ == "__main__":
    unittest.main()
