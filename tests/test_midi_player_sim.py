import sys
import os
import time
import types
import unittest
from unittest.mock import patch

# Add server directory to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "server")))

from midi_player import MidiBeatSync  # noqa: E402


class FakeMsg:
    def __init__(self, msg_type="note_on", time_delta=0.0, is_meta=False, tempo=500000):
        self.type = msg_type
        self.time = time_delta
        self.is_meta = is_meta
        self.tempo = tempo


class FakeOutPort:
    def __init__(self):
        self.sent = []
        self.closed = False

    def send(self, msg):
        self.sent.append(msg)

    def close(self):
        self.closed = True


def build_fake_mid():
    msgs = [
        FakeMsg("set_tempo", time_delta=0.0, is_meta=True, tempo=500000),
        FakeMsg("note_on", time_delta=0.05),
        FakeMsg("note_off", time_delta=0.05),
    ]

    class _FakeMid:
        tracks = [msgs]

        def __iter__(self):
            return iter(msgs)

    return _FakeMid()


class TestMidiPlayerSim(unittest.TestCase):
    @patch("midi_player.mido")
    def test_threaded_playback_sends_messages(self, mido_mock):
        # Arrange fake mido
        fake_port = FakeOutPort()
        mido_mock.set_backend.return_value = None
        mido_mock.tempo2bpm.return_value = 120.0
        mido_mock.open_output.return_value = fake_port

        def midi_file_side_effect(path=None):
            return build_fake_mid()

        mido_mock.MidiFile.side_effect = midi_file_side_effect

        player = MidiBeatSync("dummy.mid")

        # Act
        player.start()

        # Wait until both note_on and note_off are sent, or timeout
        deadline = time.time() + 0.3
        while len(fake_port.sent) < 2 and time.time() < deadline:
            time.sleep(0.01)

        player.end()

        # Assert
        sent_types = [msg.type for msg in fake_port.sent]
        self.assertIn("note_on", sent_types)
        self.assertIn("note_off", sent_types)
        self.assertTrue(fake_port.closed)

    @patch("midi_player.mido")
    def test_bpm_change_is_applied(self, mido_mock):
        fake_port = FakeOutPort()
        mido_mock.set_backend.return_value = None
        mido_mock.tempo2bpm.return_value = 120.0
        mido_mock.open_output.return_value = fake_port
        mido_mock.MidiFile.side_effect = lambda path=None: build_fake_mid()

        player = MidiBeatSync("dummy.mid")
        player.start()
        player.set_BPM(90.0)

        # Let the command queue be processed
        time.sleep(0.05)
        player.end()

        self.assertEqual(player.walkingBPM, 90.0)


if __name__ == "__main__":
    unittest.main()

