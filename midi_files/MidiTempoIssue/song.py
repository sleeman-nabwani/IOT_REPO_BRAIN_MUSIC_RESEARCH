import time
import mido

class MidiBeatSync :

    def __init__(self, midi_path):
        self.mid = mido.MidiFile(midi_path) #load the midi file
        self.songBPM = self._extract_song_bpm()

        if self.songBPM is None:
            raise ValueError("This MIDI file has no tempo. ERROR")

        self.walkingBPM = self.songBPM
        self.TempoFactor = 1.0
        self.outport = mido.open_output()


    def _extract_song_bpm(self):
        for track in self.mid.tracks:
            for msg in track:
                if msg.type == "set_tempo":
                    return mido.tempo2bpm(msg.tempo)
        return None


    def set_BPM(self, bpm : float):
        self.walkingBPM = bpm
        self.TempoFactor = self.songBPM / self.walkingBPM


    def play(self):
        for msg in self.mid:
            time.sleep(msg.time * self.TempoFactor)
            if not msg.is_meta:
                self.outport.send(msg)
            yield

