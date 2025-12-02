import mido

MIDI_PATH = r"C:\Users\USER\Desktop\midi_files_Technion_March1.mid"
mid = mido.MidiFile(MIDI_PATH)

print("Scanning MIDI...")

channels = {}
notes = {}

for i, track in enumerate(mid.tracks):
    print(f"\n=== Track {i}: {track.name} ===")
    for msg in track:
        if msg.type == "note_on":
            channels[msg.channel] = channels.get(msg.channel, 0) + 1
            notes[msg.note] = notes.get(msg.note, 0) + 1
            print(f"NOTE_ON → note={msg.note}, channel={msg.channel}, velocity={msg.velocity}")
