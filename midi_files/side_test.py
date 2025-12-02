import threading
import time
import random
from song import MidiBeatSync
from BPMcalculations import BpmCalculator

# ---- MIDI FILE ---- #
MIDI_PATH = r"C:\Users\USER\Desktop\midi_files_Technion_March1.mid"

# ---- OBJECTS ---- #
bpmCalc = BpmCalculator(size=3)
midiSync = MidiBeatSync(MIDI_PATH)


# ---- MIDI PLAYBACK THREAD ---- #
def midi_thread():
    print("🎵 MIDI thread started.")
    for _ in midiSync.play():
        pass
    print("⚠ MIDI thread ended (this should NOT happen!)")


# ---- WALK SIMULATION ---- #
def walking_simulation():
    print("\n🚶 WALK SIMULATION STARTED\n")

    # ONLY TWO PHASES
    phases = [
        ("SLOW WALK", 90),
        ("SPRINT WALK", 200),
    ]

    while True:
        for label, bpm_target in phases:

            print(f"\n➡ Phase: {label}  (≈ {bpm_target} BPM) for 20 seconds")

            # base interval between steps
            base_interval = 60.0 / bpm_target
            phase_end = time.time() + 20

            while time.time() < phase_end:

                # small human-like variation (±5%)
                jitter = random.uniform(-0.05, 0.05) * base_interval
                step_interval = base_interval + jitter

                time.sleep(step_interval)

                result = bpmCalc.add_step()
                if result is None:
                    print("First step recorded.")
                    continue

                instant, smooth = result

                # sync MIDI tempo to smoothed BPM
                midiSync.set_BPM(smooth)

                print(
                    f"[{label}] Step → instant={instant:.1f}, "
                    f"smooth={smooth:.1f}, "
                    f"TempoFactor={midiSync.TempoFactor:.3f}"
                )


# ---- PROGRAM ENTRY POINT ---- #
if __name__ == "__main__":
    print("🎵 STARTING MIDI THREAD...")
    t = threading.Thread(target=midi_thread, daemon=True)
    t.start()

    print("🚶 STARTING WALK SIMULATION...")
    walking_simulation()   # runs forever
