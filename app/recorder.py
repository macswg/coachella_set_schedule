"""
Recording trigger implementation — swap this file per show.

This is the only file that needs to change between productions.
The rest of the trigger engine (triggers.py) never needs to be touched.

Required interface:
    start_recording(act_name: str) -> None
    stop_recording(act_name: str) -> None

Both functions should be non-blocking (return quickly). If your integration
is slow, wrap it in a thread.
"""


def start_recording(act_name: str) -> None:
    """
    Called automatically X minutes before an act's scheduled start.

    Replace this body with your show's recording integration. Examples:

    HTTP API:
        import requests
        requests.post("http://192.168.1.50:8080/record/start", json={"channel": act_name}, timeout=3)

    Shell command:
        import subprocess
        subprocess.Popen(["record-start", "--name", act_name])

    OSC message:
        from pythonosc.udp_client import SimpleUDPClient
        client = SimpleUDPClient("192.168.1.50", 9000)
        client.send_message("/record/start", act_name)
    """
    print(f"[recorder] start_recording: {act_name!r}")


def stop_recording(act_name: str) -> None:
    """
    Called when the operator clicks "Stop Recording" on the /edit page.
    Never called automatically.

    Replace this body with your show's recording integration. Examples:

    HTTP API:
        import requests
        requests.post("http://192.168.1.50:8080/record/stop", json={"channel": act_name}, timeout=3)

    Shell command:
        import subprocess
        subprocess.Popen(["record-stop", "--name", act_name])

    OSC message:
        from pythonosc.udp_client import SimpleUDPClient
        client = SimpleUDPClient("192.168.1.50", 9000)
        client.send_message("/record/stop", act_name)
    """
    print(f"[recorder] stop_recording: {act_name!r}")
