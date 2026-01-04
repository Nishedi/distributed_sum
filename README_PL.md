# Distributed Sum - Rozproszone rozwiązywanie problemu CVRP

## 1. Struktura projektu

Projekt zawiera implementację rozproszonego algorytmu Branch and Bound dla problemu komiwojażera z wieloma pojazdami (Capacitated Vehicle Routing Problem - CVRP).

### Struktura katalogów

```
distributed_sum/
├── cpp/                          # Implementacje C++
│   ├── distributed_bnb.cpp       # Główny algorytm Branch and Bound w C++
│   ├── sum_array.cpp             # Pomocnicze funkcje do sumowania (legacy)
│   └── libcvrp.so                # Skompilowana biblioteka współdzielona
├── python/                       # Warstwa orkiestracji w Pythonie
│   ├── run_ray.py                # Główny skrypt uruchamiający testy
│   ├── ray_cvrp.py               # Funkcje Ray do dystrybucji zadań
│   └── greedy.py                 # Algorytm zachłanny do znajdowania górnego ograniczenia
├── results/                      # Wyniki eksperymentów
│   ├── test_one_vs_all_16_sorted.csv  # Posortowane wyniki dla 16 miast
│   └── *.csv                     # Inne pliki wynikowe
├── bnb_classic.py                # Klasyczna implementacja BnB w czystym Pythonie
├── sort_results.py               # Skrypt do sortowania wyników CSV
├── compile_and_send.sh           # Skrypt do kompilacji i dystrybucji biblioteki na klaster
├── nodes.txt                     # Lista węzłów w klastrze
└── venv/                         # Środowisko wirtualne Python
```

### Pliki konfiguracyjne

- **nodes.txt** - lista adresów węzłów w klastrze Ray
- **compile_and_send.sh** - automatyzuje kompilację biblioteki C++ i dystrybucję na wszystkie węzły klastra
- **.gitignore** - ignoruje pliki środowiska wirtualnego, cache Pythona i pliki obiektowe

---

## 2. Implementacja (szczegółowo)

### 2.1. Problem CVRP (Capacitated Vehicle Routing Problem)

**Problem:**
- Dany jest zbiór n miast z współrzędnymi (x, y)
- Miasto 0 jest depotem (punkt startowy i końcowy)
- Każdy pojazd ma ograniczoną pojemność C (liczba miast do odwiedzenia)
- Cel: Znaleźć zestaw tras minimalizujący całkowity dystans przy zachowaniu ograniczenia pojemności

**Parametry:**
- `n` - liczba miast (włącznie z depotem)
- `C` - pojemność pojazdu (maksymalna liczba miast w jednej trasie)
- `dist[i][j]` - macierz odległości euklidesowych między miastami

### 2.2. Algorytm Branch and Bound (BnB)

#### Główna klasa `CVRP_BnB` (cpp/distributed_bnb.cpp)

**Struktura klasy:**
```cpp
class CVRP_BnB {
public:
    double** dist;        // Macierz odległości
    int n;                // Liczba miast
    int C;                // Pojemność pojazdu
    double best_cost;     // Najlepszy znaleziony koszt
    int cut;              // Licznik odciętych gałęzi
    int checks;           // Licznik sprawdzonych węzłów
}
```

**Kluczowe metody:**

1. **`lower_bound()`** - Oblicza dolne ograniczenie kosztu
   - Dla każdego nieodwiedzonego miasta znajduje minimalną odległość do innego miasta
   - Suma tych minimalnych odległości stanowi pesymistyczne oszacowanie pozostałego kosztu
   - Używane do przycinania gałęzi, które nie mogą dać lepszego rozwiązania

2. **`branch_and_bound()`** - Rekurencyjne przeszukiwanie drzewa rozwiązań
   ```
   Warunek zakończenia:
   - Jeśli wszystkie miasta odwiedzone → zwróć koszt + powrót do depotu
   
   Cięcie (pruning):
   - Oblicz lower_bound dla bieżącego stanu
   - Jeśli current_cost + lower_bound >= best_cost → obetnij gałąź
   
   Rozgałęzienie (branching):
   - Dla każdego nieodwiedzonego miasta (jeśli load + 1 <= C):
     * Dodaj miasto do trasy
     * Rekurencyjnie wywołaj BnB
     * Usuń miasto (backtracking)
   - Jeśli bieżąca trasa niepusta:
     * Rozpocznij nową trasę (nowy pojazd)
     * Rekurencyjnie wywołaj BnB
   ```

#### Funkcje API C (extern "C")

**`solve_from_first_city(dist, n, C, first_city, cutting, bound_value)`**
- Rozwiązuje problem startując od depotu → first_city
- Parametry:
  - `dist` - macierz odległości (double**)
  - `n` - liczba miast
  - `C` - pojemność pojazdu
  - `first_city` - indeks pierwszego miasta do odwiedzenia
  - `cutting` - czy włączyć przycinanie gałęzi (1/0)
  - `bound_value` - początkowe górne ograniczenie
- Zwraca: minimalny koszt znaleziony dla tej podprzestrzeni

**`solve_from_two_cities(dist, n, C, first_city, second_city, cutting, bound_value)`**
- Rozwiązuje problem dla trasy: depot → first_city → second_city → ...
- Tworzy drobniejsze zadania dla lepszego balansowania obciążenia
- Parametry jak wyżej plus `second_city`

### 2.3. Algorytm zachłanny (Greedy 1-NN)

**Plik: `python/greedy.py`**

Algorytm zachłanny znajduje szybkie, ale nieoptymalne rozwiązanie:

```python
def greedy_cvrp_1nn(dist, C=5):
    1. Start w depocie (miasto 0)
    2. Dopóki są nieodwiedzone miasta:
       - Jeśli pojazd pełny (load == C):
         * Wróć do depotu
         * Rozpocznij nową trasę
       - Znajdź najbliższe nieodwiedzone miasto
       - Dodaj je do trasy
       - Zwiększ obciążenie
    3. Wróć do depotu
    4. Zwróć trasę i całkowity koszt
```

**Zastosowanie:** Koszt z algorytmu zachłannego używany jest jako:
- Górne ograniczenie początkowe (`bound_value`) dla BnB
- Znacznie przyspiesza algorytm BnB poprzez wcześniejsze odcinanie gałęzi

### 2.4. Rozproszone przetwarzanie z Ray

**Plik: `python/ray_cvrp.py`**

#### Ray Remote Functions

**`@ray.remote def solve_city(...)`**
- Wrapper Pythona dla funkcji C++ `solve_from_first_city`
- Konwertuje macierz NumPy na format ctypes wymagany przez C++
- Każde wywołanie wykonywane jest na innym węźle klastra Ray
- Zwraca najlepszy koszt dla danego pierwszego miasta

**`@ray.remote def solve_city_pair(...)`**
- Wrapper dla funkcji C++ `solve_from_two_cities`
- Tworzy zadania dla par miast (city1, city2)
- Lepsze balansowanie obciążenia przez zwiększenie liczby zadań

#### Ray Actor - BoundTracker

```python
@ray.remote
class BoundTracker:
    def __init__(self, initial_bound):
        self.best_bound = initial_bound
    
    def update_bound(self, new_bound):
        # Aktualizuje globalne ograniczenie jeśli znaleziono lepsze
        if new_bound < self.best_bound:
            self.best_bound = new_bound
            return True
        return False
    
    def get_bound(self):
        # Zwraca aktualne najlepsze ograniczenie
        return self.best_bound
```

**Zastosowanie:**
- Współdzielony stan między wszystkimi workerami
- Każdy worker może sprawdzić aktualne najlepsze ograniczenie
- Każdy worker aktualizuje ograniczenie gdy znajdzie lepsze rozwiązanie
- Znacznie poprawia efektywność przez lepsze przycinanie gałęzi

#### Konwersja danych NumPy → ctypes

```python
# NumPy array → double** (wskaźnik do tablicy wskaźników)
c_mat = (ctypes.POINTER(ctypes.c_double) * n)()
for i in range(n):
    row = (ctypes.c_double * n)(*dist_np[i])
    c_mat[i] = row
```

### 2.5. Skrypt główny - Testy porównawcze

**Plik: `python/run_ray.py`**

Wykonuje 5 testów porównawczych:

#### Test 1: BnB bez współdzielonego ograniczenia
```python
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
```
- Każdy worker rozwiązuje podproblem dla jednego pierwszego miasta
- Brak komunikacji między workerami
- Początkowy bound = nieskończoność (999999999)

#### Test 2: BnB_SP (Starting Point) bez współdzielonego ograniczenia
```python
futures = [solve_city.remote(dist, C, i, 1, int(cost)) for i in range(1, n)]
```
- Jak Test 1, ale z początkowym ograniczeniem z algorytmu zachłannego
- `cost` pochodzi z `greedy_cvrp_1nn()`
- Lepsze przycinanie od początku

#### Test 3: BnB ze współdzielonym ograniczeniem
```python
bound_tracker = BoundTracker.remote(999999999)
futures = [solve_city.remote(dist, C, i, 1, 999999999, bound_tracker) 
           for i in range(1, n)]
```
- Każdy worker współdzieli `BoundTracker`
- Worker pobiera aktualny bound przed rozpoczęciem: `ray.get(bound_tracker.get_bound.remote())`
- Worker aktualizuje bound po znalezieniu lepszego rozwiązania (fire-and-forget)
- Dynamiczne przycinanie podczas obliczeń

#### Test 4: BnB_SP ze współdzielonym ograniczeniem
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) 
           for i in range(1, n)]
```
- Łączy zalety Test 2 i Test 3
- Rozpoczyna od dobrego ograniczenia (greedy)
- Plus dynamiczna aktualizacja podczas obliczeń

#### Test 5: BnB z drobnymi zadaniami (pary miast)
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city_pair.remote(dist, C, i, j, 1, int(cost), bound_tracker)
           for i in range(1, n) for j in range(1, n) if i != j]
```
- Tworzy zadania dla par miast zamiast pojedynczych miast
- Liczba zadań: (n-1) × (n-2) zamiast (n-1)
- **Najlepsza wydajność** dzięki:
  - Lepszemu balansowaniu obciążenia (więcej małych zadań)
  - Współdzielonemu ograniczeniu
  - Początkowemu ograniczeniu z greedy

### 2.6. Integracja z klastrem

**Kompilacja i dystrybucja:**
```bash
# compile_and_send.sh
g++ -O3 -fPIC -shared cpp/distributed_bnb.cpp -o cpp/libcvrp.so
scp cpp/libcvrp.so cluster@cluster600:/home/cluster/distributed_sum/cpp
scp cpp/libcvrp.so cluster@cluster601:/home/cluster/distributed_sum/cpp
# ... dla wszystkich węzłów
```

**Inicjalizacja Ray:**
```python
ray.init(address="auto")  # Łączy się z istniejącym klastrem Ray
```

**Uruchomienie na klastrze:**
```bash
# Na węźle głównym
ray start --head --port=6379

# Na węzłach roboczych
ray start --address="<head-node-ip>:6379"

# Uruchomienie testu
python python/run_ray.py --n 16 --C 5 --fn results/test.csv --ct "Cluster multithread"
```

### 2.7. Pomiar wydajności

Każdy test mierzy:
- **preparing_time** - czas na utworzenie zadań Ray (futuresów)
- **computing_time** - czas na wykonanie obliczeń przez workery
- **time_sec** - całkowity czas (preparing + computing)
- **best_cost** - najlepszy znaleziony koszt
- **cluster_type** - konfiguracja klastra (Single Thread, Single node multithread, Cluster single threads, Cluster multithread)

Wyniki zapisywane są do pliku CSV z polami:
```
n, C, method, best_cost, time_sec, preparing_time, computing_time, cluster_type
```

---

## 3. Aktualne wyniki - analiza pliku `results/test_one_vs_all_16_sorted.csv`

### 3.1. Parametry testu

- **Liczba miast (n):** 16 (włącznie z depotem)
- **Pojemność pojazdu (C):** 5 miast
- **Współrzędne miast:** Losowe z zakresu [0, 10000]
- **Najlepszy znaleziony koszt:** 35652.0 (w większości testów)

### 3.2. Tabela wyników

| Test | Metoda | Konfiguracja | Czas [s] | Preparing [s] | Computing [s] | Koszt |
|------|--------|--------------|----------|---------------|---------------|-------|
| 1 | BnB bez współdzielenia | Single Thread | 2598.95 | 0.006 | 2598.95 | 35652.11 |
| 1 | BnB bez współdzielenia | Single node multithread | 522.75 | 0.007 | 522.74 | 35652.11 |
| 1 | BnB bez współdzielenia | Cluster single threads | 363.14 | 0.006 | 363.14 | 35652.11 |
| 1 | BnB bez współdzielenia | Cluster multithread | 246.89 | 0.006 | 246.88 | 35652.11 |
| 2 | BnB_SP bez współdzielenia | Single Thread | 2172.19 | 0.021 | 2172.17 | 35652.11 |
| 2 | BnB_SP bez współdzielenia | Single node multithread | 442.81 | 0.007 | 442.80 | 35652.11 |
| 2 | BnB_SP bez współdzielenia | Cluster single threads | 295.41 | 0.020 | 295.39 | 35652.11 |
| 2 | BnB_SP bez współdzielenia | Cluster multithread | 246.67 | 0.020 | 246.65 | 35652.11 |
| 3 | BnB ze współdzieleniem | Single Thread | 607.79 | 0.018 | 607.77 | 35652.0 |
| 3 | BnB ze współdzieleniem | Single node multithread | 311.04 | 0.018 | 311.02 | 35652.0 |
| 3 | BnB ze współdzieleniem | Cluster single threads | 242.25 | 0.019 | 242.24 | 35652.0 |
| 3 | BnB ze współdzieleniem | Cluster multithread | 238.51 | 0.020 | 238.49 | 35652.11 |
| 4 | BnB_SP ze współdzieleniem | Single Thread | 607.16 | 0.024 | 607.14 | 35652.0 |
| 4 | BnB_SP ze współdzieleniem | Single node multithread | 307.68 | 0.008 | 307.67 | 35652.0 |
| 4 | BnB_SP ze współdzieleniem | Cluster single threads | 228.40 | 0.009 | 228.39 | 35652.0 |
| 4 | BnB_SP ze współdzieleniem | Cluster multithread | 247.02 | 0.008 | 247.01 | 35652.11 |
| 5 | BnB pary miast | Single Thread | 432.38 | 0.093 | 432.29 | 35652.0 |
| 5 | BnB pary miast | Single node multithread | 151.66 | 0.098 | 151.56 | 35652.0 |
| 5 | BnB pary miast | Cluster single threads | **99.73** | 0.102 | **99.63** | 35652.0 |
| 5 | BnB pary miast | Cluster multithread | 138.67 | 0.123 | 138.55 | 35652.0 |

### 3.3. Analiza wyników

#### Najlepsze wyniki (najmniejszy czas):

🏆 **Test 5 (BnB pary miast) - Cluster single threads: 99.73s**
- Najszybszy sposób rozwiązania problemu
- Drobne zadania zapewniają równomierne obciążenie klastra
- Współdzielone ograniczenie przyspiesza obliczenia

#### Przyspieszenie względem bazowej implementacji:

| Metoda | Single Thread | Najlepsza konfiguracja | Przyspieszenie |
|--------|---------------|------------------------|----------------|
| Test 1 (BnB podstawowy) | 2598.95s | 246.89s (Cluster MT) | **10.5x** |
| Test 2 (BnB_SP) | 2172.19s | 246.67s (Cluster MT) | **8.8x** |
| Test 3 (BnB shared) | 607.79s | 238.51s (Cluster MT) | **2.5x** |
| Test 4 (BnB_SP shared) | 607.16s | 228.40s (Cluster ST) | **2.7x** |
| Test 5 (BnB pary) | 432.38s | 99.73s (Cluster ST) | **4.3x** |

#### Wnioski:

1. **Wpływ współdzielonego ograniczenia:** 
   - Test 1 vs Test 3: Współdzielone ograniczenie redukuje czas z 2598.95s do 607.79s (4.3x) w konfiguracji Single Thread
   - Znacząca poprawa nawet bez dystrybuowania na wiele maszyn

2. **Wpływ początkowego ograniczenia z greedy:**
   - Test 1 vs Test 2: Greedy bound redukuje czas z 2598.95s do 2172.19s (1.2x)
   - Mniejszy wpływ niż współdzielone ograniczenie, ale ciągle pomocny

3. **Wpływ drobnych zadań (Test 5):**
   - Znacząco lepsza wydajność od Test 4 na klastrze
   - Cluster single threads (99.73s) lepszy niż Cluster multithread (138.67s)
   - Więcej zadań = lepsze balansowanie obciążenia

4. **Single thread vs Multithread na klastrze:**
   - W większości przypadków cluster multithread jest szybszy
   - **Wyjątek: Test 5** - cluster single threads szybszy (99.73s vs 138.67s)
   - Prawdopodobnie z powodu overhead'u zarządzania wątkami przy dużej liczbie małych zadań

5. **Skalowanie:**
   - Przejście z single node na cluster daje znaczące przyspieszenie (2-5x)
   - Optymalna konfiguracja zależy od charakterystyki zadań

### 3.4. Rekomendacje

**Dla problemu CVRP z 16 miastami i podobnymi:**
1. Używaj **Test 5 (BnB z parami miast) + Cluster single threads**
2. Włącz współdzielone ograniczenie (`BoundTracker`)
3. Użyj algorytmu zachłannego dla początkowego ograniczenia
4. Rozważ single thread na klastrze dla dużej liczby małych zadań

**Optymalizacje dla większych problemów (n > 16):**
- Test 5 z parami miast da jeszcze większe przyspieszenie
- Można rozważyć podział na trójki miast dla n > 20
- Współdzielone ograniczenie staje się bardziej krytyczne

---

## 4. Uruchomienie projektu

### 4.1. Wymagania

- Python 3.8+
- Ray (distributed computing framework)
- NumPy
- GCC/G++ (dla kompilacji C++)

### 4.2. Instalacja

```bash
# Utwórz środowisko wirtualne
python3 -m venv venv
source venv/bin/activate

# Zainstaluj zależności
pip install ray numpy

# Skompiluj bibliotekę C++
g++ -O3 -fPIC -shared cpp/distributed_bnb.cpp -o cpp/libcvrp.so
```

### 4.3. Uruchomienie testów

**Klaster pojedynczego węzła:**
```bash
python python/run_ray.py --n 14 --C 5 --fn results/test.csv --ct "single node"
```

**Klaster wielowęzłowy:**
```bash
# Węzeł główny
ray start --head --port=6379

# Węzły robocze (na każdym)
ray start --address="<head-ip>:6379"

# Uruchom test
python python/run_ray.py --n 16 --C 5 --fn results/test_cluster.csv --ct "cluster"
```

### 4.4. Analiza wyników

```bash
# Posortuj wyniki według metody
python sort_results.py results/test.csv

# Wyświetl posortowane wyniki
cat results/test_sorted.csv
```

---

## 5. Dalszy rozwój

### Możliwe usprawnienia:

1. **Adaptacyjny podział zadań:** Dynamiczne dzielenie zadań na podstawie obciążenia workerów
2. **Cache wyników:** Memoizacja powtarzających się podproblemów
3. **Lepsza heurystyka dolnego ograniczenia:** Bardziej dokładne oszacowania dla szybszego przycinania
4. **GPU acceleration:** Wykorzystanie GPU dla operacji macierzowych
5. **Checkpoint/restart:** Możliwość wznowienia obliczeń po przerwaniu

---

## 6. Autor i licencja

Projekt implementuje rozproszone rozwiązanie problemu CVRP przy użyciu algorytmu Branch and Bound.

**Technologie:**
- C++ (algorytm BnB)
- Python (orkiestracja)
- Ray (distributed computing)
- ctypes (integracja Python-C++)

**Projekt demonstracyjny** ilustrujący techniki:
- Rozproszonego przetwarzania
- Integracji Python-C++
- Algorytmów Branch and Bound
- Optymalizacji przez współdzielony stan
