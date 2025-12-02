import time
import mido

# DRUM PARAMETERS
DRUM_NOTES = {35, 57}
DRUM_CHANNEL = 9            # the drum track is on channel 9


class MidiBeatSync:

    def __init__(self, midi_path):
        self.mid = mido.MidiFile(midi_path)

        self.songBPM = self._extract_MIDI_bpm()
        if self.songBPM is None:
            raise ValueError("ERROR: No tempo (set_tempo) found in MIDI file.")

        self.walkingBPM = self.songBPM
        self.TempoFactor = 1.0

        self.nextDrumPredicted = None     # predicted drum time (in real seconds)
        self.outport = mido.open_output() # MIDI device output


    def _extract_MIDI_bpm(self):
        for track in self.mid.tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    return mido.tempo2bpm(msg.tempo)
        return None


    # ---------------------------------------------------------
    # Update player tempo based on smoothed walking BPM
    # ---------------------------------------------------------
    def set_BPM(self, bpm):
        if bpm <= 0:
            print("Ignoring invalid BPM <= 0.")
            return

        self.walkingBPM = bpm
        baseFactor = self.songBPM / self.walkingBPM   # main tempo change

        # If this message is a drum hit we care about, save WHEN it is supposed to happen.
        # Used later for "phase correction" to align drum hits with footsteps.
        if self.nextDrumPredicted is not None:
            now = time.time()
            phase_error = now - self.nextDrumPredicted   # positive = drum late

            k = 0.04   # correction gain
            correction = 1 - k * phase_error

            # limit strength to avoid jumps
            correction = max(0.90, min(1.10, correction))
        else:
            correction = 1.0

        self.TempoFactor = baseFactor * correction


    def play(self):
        start_time = time.time()  # We only use this to print timestamps (like +3.512s) for debugging drum hits. It doesn’t affect syncing.

        while True:
            for msg in self.mid: # iterate through every MIDI event in the file

                # Calculate the exact real-world time when this MIDI event should be played.
                # msg.time = delay (in seconds) since previous event, TempoFactor speeds/slows it.
                predicted = time.time() + msg.time * self.TempoFactor

                # If this message is a drum hit we care about, save WHEN it is supposed to happen.
                # Used later for "phase correction" to align drum hits with footsteps.
                if msg.type == "note_on" and msg.channel == DRUM_CHANNEL:
                    if msg.note in DRUM_NOTES:
                        self.nextDrumPredicted = predicted

                # Wait (busy-wait) until the predicted time arrives before sending the note.
                while time.time() < predicted:
                    pass

                if not msg.is_meta: #msg.is_meta = meta messages (do NOT make sound)
                    self.outport.send(msg) # send it to the MIDI output so we hear it.

                # DRUM ACTUALLY PLAYED — DEBUG PRINT
                if msg.type == "note_on" and msg.channel == DRUM_CHANNEL:
                    if msg.note in DRUM_NOTES:
                        actual = time.time()
                        print(f"DRUM HIT → Note {msg.note}   at +{actual - start_time:.3f}s")

                yield msg  # pause playback and give control back to main program; allow BPM updates while music plays

            # when file ends → restart
            self.mid = mido.MidiFile(self.mid.filename)

