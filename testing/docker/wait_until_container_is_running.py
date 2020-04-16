import subprocess
import sys
import time

timeout = 40

start_time = time.time()


class TimeoutException(Exception):
    pass


while True:
    args = [
        "docker",
        "inspect",
        "-f",
        '""{{.State.Health}}""',
        sys.argv[1],
    ]
    result = subprocess.run(args, capture_output=True)
    if "healthy 0" in result.stdout.decode():
        break
    if time.time() - start_time > timeout:
        raise TimeoutException(
            "Waiting for docker image to be healthy took too long. Is docker running?"
        )
