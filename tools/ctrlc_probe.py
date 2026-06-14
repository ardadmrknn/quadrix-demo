import os
import signal
import subprocess
import sys
import time


STATUS_CONTROL_C_EXIT = 0xC000013A


def main() -> int:
    # Ensure we run from the game folder so relative paths behave like normal launch.
    game_dir = os.path.dirname(os.path.abspath(__file__))
    game_dir = os.path.abspath(os.path.join(game_dir, ".."))
    os.chdir(game_dir)

    # Start the game as a child process.
    # CREATE_NEW_PROCESS_GROUP enables CTRL_BREAK_EVENT delivery on Windows.
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    proc = subprocess.Popen(
        [sys.executable, "-u", "main.py"],
        creationflags=CREATE_NEW_PROCESS_GROUP,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    delay_s = float(os.environ.get("COPILOT_CTRLC_DELAY", "3.0"))
    print(f"[probe] started pid={proc.pid}, waiting {delay_s:.1f}s then sending Ctrl+C...", flush=True)
    time.sleep(delay_s)

    # Prefer CTRL_C_EVENT (closer to Ctrl+C) but also send CTRL_BREAK_EVENT shortly
    # after (some pygame apps ignore CTRL_C_EVENT but respond to CTRL_BREAK_EVENT).
    sent = []
    try:
        print("[probe] --- sending Ctrl+C (CTRL_C_EVENT) ---", flush=True)
        proc.send_signal(signal.CTRL_C_EVENT)
        sent.append("CTRL_C_EVENT")
        time.sleep(0.25)
        print("[probe] --- sending Ctrl+Break (CTRL_BREAK_EVENT) ---", flush=True)
        proc.send_signal(signal.CTRL_BREAK_EVENT)
        sent.append("CTRL_BREAK_EVENT")
    except Exception as exc:
        print(f"[probe] failed to send ctrl event(s): {exc}", flush=True)
        proc.terminate()

    try:
        rc = proc.wait(timeout=10)
        output = ""
        if proc.stdout is not None:
            try:
                output = proc.stdout.read() or ""
            except Exception:
                output = ""
        if output.strip():
            print("[probe] --- child output (combined) ---")
            print(output.rstrip("\n"))
            print("[probe] --- end child output ---")

        if rc is None:
            print("[probe] --- child exit code: (none) ---", flush=True)
            return 0

        # rc may be signed on Windows; normalize to unsigned 32-bit for comparison.
        rc_u32 = rc & 0xFFFFFFFF
        print(f"[probe] --- child exit code: {rc} (0x{rc_u32:08X}), sent={'+'.join(sent) if sent else None} ---", flush=True)
        if rc_u32 == STATUS_CONTROL_C_EXIT:
            print("[probe] note: 0xC000013A = STATUS_CONTROL_C_EXIT (Ctrl+C/Break ile durduruldu)", flush=True)
        return int(rc)
    except subprocess.TimeoutExpired:
        print("[probe] --- child did not exit; terminating ---", flush=True)
        proc.terminate()
        rc = proc.wait(timeout=5)
        print(f"[probe] --- child exit code after terminate: {rc} ---", flush=True)
        return int(rc) if rc is not None else 1


if __name__ == "__main__":
    raise SystemExit(main())
