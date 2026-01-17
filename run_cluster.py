from fabric import Connection
from invoke.exceptions import UnexpectedExit
import argparse
import subprocess
import time

user = "cluster"

parser = argparse.ArgumentParser(description="Starting cluster workers for Ray.")
parser.add_argument("--threads", type=str, default="multithread", help="Mode of CPU's working threads: multithread or singlethread")
parser.add_argument("--nodes", type=int, default=8, help="Number of nodes to start")
parser.add_argument("--stop", action='store_true', help="Stop the Ray cluster instead of starting it")
args = parser.parse_args()

threads = args.threads
nodes = args.nodes
stop = args.stop


head_cmd = (
    "source ~/distributed_sum/venv/bin/activate && "
    "ray stop; "
    "ray start --head --port=6379 --num-cpus 0"
)
if stop:
    head_cmd = (
        "source ~/distributed_sum/venv/bin/activate && "
        "ray stop"
    )
    print(f"--- Zatrzymywanie klastra Ray na wszystkich węzłach ---")
    for host_id in range(0,nodes+1):
        host=f"cluster60{host_id}"
        print(f"--- Przetwarzanie hosta: {host} ---")
        try:
            c = Connection(
                host=host,
                user=user,

            )

            result = c.run(head_cmd, hide=True)
            print(f"[SUKCES] {host}: Ray zatrzymany.")

        except UnexpectedExit as e:
            print(f"[BŁĄD] {host}: Komenda zwróciła błąd: {e}")
        except Exception as e:
            print(f"[BŁĄD] {host}: Nie udało się połączyć: {e}")

    print("Zakończono zatrzymywanie klastra.")
    exit(0)

print(f"--- Uruchamianie HEAD NODE (lokalnie) ---")
try:
    subprocess.run(head_cmd, shell=True, executable='/bin/bash', check=True)
    print("[SUKCES] Head node uruchomiony.")
except subprocess.CalledProcessError as e:
    print(f"[BŁĄD] Nie udało się uruchomić Head Node: {e}")
    exit(1)


print("Czekanie 10 sekund na inicjalizację klastra...")
time.sleep(10)


if threads == "multithread":
    cmd = (
        "source ~/distributed_sum/venv/bin/activate && "
        "ray stop; "  
        "ray start --address='156.17.41.136:6379'"
    )
else:
    cmd = (
        "source ~/distributed_sum/venv/bin/activate && "
        "ray stop; "
        "ray start --address='156.17.41.136:6379' --num-cpus 1"
    )

print(f"Rozpoczynam podłączanie workerów do klastra Ray...")

for host_id in range(0,nodes+1):
    host=f"cluster60{host_id}"
    print(f"--- Przetwarzanie hosta: {host} ---")
    try:

        c = Connection(
            host=host, 
            user=user, 

        )

        result = c.run(cmd, hide=True)
        print(f"[SUKCES] {host}: Ray uruchomiony.")
        
    except UnexpectedExit as e:
        print(f"[BŁĄD] {host}: Komenda zwróciła błąd: {e}")
    except Exception as e:
        print(f"[BŁĄD] {host}: Nie udało się połączyć: {e}")

print("Zakończono.")
