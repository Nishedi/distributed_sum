from fabric import Connection
from invoke.exceptions import UnexpectedExit

# Lista adresów IP lub nazw hostów workerów


user = "cluster"  # Użytkownik SSH na zdalnych maszynach


# Komenda do wykonania.
# Uwaga: Łączymy komendy operatorem "&&" lub ";", aby działy się w jednej sesji.
# "source" działa tylko w bieżącej powłoce, więc kolejne komendy muszą być w tej samej linii.
cmd = (
    "source ~/distributed_sum/venv/bin/activate && "
    "ray stop; "  # Średnik, aby wykonać start nawet jeśli stop zwróci błąd (np. ray nie działał)
    "ray start --address='156.17.41.136:6379'"
)

print(f"Rozpoczynam podłączanie workerów do klastra Ray...")

for host_id in range(0,9):
    host=f"cluster60{host_id}"
    print(f"--- Przetwarzanie hosta: {host} ---")
    try:
        # Nawiązanie połączenia
        # Jeśli masz skonfigurowane klucze SSH w systemie (ssh-agent), connect_kwargs można pominąć
        c = Connection(
            host=host, 
            user=user, 

        )
        
        # Wykonanie komendy
        result = c.run(cmd, hide=True) # hide=True ukrywa output, chyba że chcesz go widzieć
        
        print(f"[SUKCES] {host}: Ray uruchomiony.")
        
    except UnexpectedExit as e:
        print(f"[BŁĄD] {host}: Komenda zwróciła błąd: {e}")
    except Exception as e:
        print(f"[BŁĄD] {host}: Nie udało się połączyć: {e}")

print("Zakończono.")
