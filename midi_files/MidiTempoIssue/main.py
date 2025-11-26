from song import MidiBeatSync
import time
import random

def main():
    midi_path = r"C:\Users\USER\Desktop\Celine_Dion_-_All_By_Myself.mid"

    # create player
    player = MidiBeatSync(midi_path)

    # generator (plays 1 MIDI message each next())
    playback = player.play()

    # current simulated BPM
    current_bpm = player.songBPM
    player.set_BPM(current_bpm)

    # time window before BPM changes
    next_change_time = time.time() + random.uniform(2, 7)

    while True:
        try:
            next(playback)  # play one MIDI event
        except StopIteration:
            break  # end of song

        # if it’s time to change BPM
        if time.time() >= next_change_time:
            # simulate “sensor sending a new BPM”
            new_bpm = random.randint(60, 500)
            print(f"Sensor update → walking BPM = {new_bpm}")

            player.set_BPM(new_bpm)

            # next sensor reading in 2–7 seconds
            next_change_time = time.time() + random.uniform(2, 7)


if __name__ == "__main__":
    main()
