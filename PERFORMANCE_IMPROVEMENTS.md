# Poprawa Wydajności Rozproszonego Branch and Bound dla CVRP

## Problem

Oryginalny kod osiągał tylko **1.7-1.8x przyspieszenie** z 9 węzłami, zamiast oczekiwanego ~9x przyspieszenia.

### Wyniki Oryginalne
```
# 9 węzłów
BnB: 48.26s
BnB_SP: 49.31s

# 1 węzeł  
BnB: 86.35s
BnB_SP: 84.40s

Przyspieszenie: tylko ~1.7-1.8x zamiast ~9x
```

## Zidentyfikowane Przyczyny

### 1. **Brak Współdzielonego Ograniczenia (Shared Bound)**
- Każdy worker działał z własnym ograniczeniem
- Workers nie dzielili się najlepszymi znalezionymi rozwiązaniami
- Brak możliwości agresywniejszego przycinania (pruning) gałęzi

### 2. **Nierównomierne Rozłożenie Pracy (Load Imbalance)**
- Zadania były dzielone według pierwszego miasta (n-1 zadań)
- Niektóre miasta prowadzą do znacznie większej przestrzeni przeszukiwania
- Najwolniejszy worker determinował całkowity czas wykonania
- Przykład: jedno zadanie może trwać 80s, podczas gdy inne 5s

### 3. **Sekwencyjne Oczekiwanie**
- `ray.get(futures)` czeka na WSZYSTKIE workery
- Czas całkowity = czas najwolniejszego workera
- Brak możliwości wcześniejszego zakończenia

## Zaimplementowane Rozwiązania

### 1. Współdzielony BoundTracker (Shared Bound Tracking)

**Plik:** `python/ray_cvrp.py`

```python
@ray.remote
class BoundTracker:
    """
    Aktor współdzielony do śledzenia globalnego najlepszego ograniczenia
    między wszystkimi workerami. Umożliwia lepsze przycinanie w algorytmie
    Branch and Bound.
    """
    def __init__(self, initial_bound):
        self.best_bound = initial_bound
    
    def update_bound(self, new_bound):
        """Aktualizuje najlepsze ograniczenie jeśli nowe jest lepsze."""
        if new_bound < self.best_bound:
            self.best_bound = new_bound
            return True
        return False
    
    def get_bound(self):
        """Pobiera aktualne najlepsze ograniczenie."""
        return self.best_bound
```

**Korzyści:**
- Workers mogą korzystać z najlepszych rozwiązań znalezionych przez innych
- Bardziej agresywne przycinanie gałęzi w drzewie przeszukiwania
- Zmniejszona ilość zbędnych obliczeń

### 2. Drobne Zadania (Fine-grained Task Distribution)

**Plik:** `cpp/distributed_bnb.cpp`

Dodano nową funkcję C++:
```cpp
double solve_from_two_cities(double** dist, int n, int C, 
                             int first_city, int second_city, 
                             int cutting, int bound_value)
```

**Plik:** `python/ray_cvrp.py`

```python
@ray.remote
def solve_city_pair(dist_np, C, city1, city2, BnB, bound_value, bound_tracker=None):
    """
    Rozwiązuje rozpoczynając od depot -> city1 -> city2, tworząc bardziej 
    szczegółowe zadania dla lepszego równoważenia obciążenia między workerami.
    """
```

**Porównanie:**
- **Strategia oryginalna:** n-1 zadań (dla n=15: 14 zadań)
- **Nowa strategia:** (n-1)*(n-2) zadań (dla n=15: 182 zadania)
- **Zwiększenie granulacji:** ~13x więcej zadań

**Korzyści:**
- Znacznie lepsze równoważenie obciążenia
- Wolniejsze zadania mogą być automatycznie rozłożone między wolne workery
- Zmniejszone ryzyko, że jeden worker będzie "wąskim gardłem"

### 3. Dynamiczne Aktualizacje Ograniczeń

Każdy worker:
1. Pobiera aktualne najlepsze ograniczenie przed rozpoczęciem
2. Używa tego ograniczenia do przycinania
3. Aktualizuje globalne ograniczenie po znalezieniu lepszego rozwiązania

```python
# Pobierz aktualne najlepsze ograniczenie
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))

# ... wykonaj obliczenia ...

# Aktualizuj globalne ograniczenie
if bound_tracker is not None and result < float('inf'):
    bound_tracker.update_bound.remote(result)
```

## Użycie

### Przed (Oryginalna Wersja)
```python
futures = [solve_city.remote(dist, C, i, 1, 999999999) for i in range(1, n)]
results = ray.get(futures)
```

### Po (Ulepszona Wersja - Współdzielone Ograniczenie)
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = [solve_city.remote(dist, C, i, 1, int(cost), bound_tracker) 
           for i in range(1, n)]
results = ray.get(futures)
```

### Po (Najbardziej Ulepszona - Drobne Zadania)
```python
bound_tracker = BoundTracker.remote(int(cost))
futures = []
for i in range(1, n):
    for j in range(1, n):
        if i != j:
            futures.append(solve_city_pair.remote(dist, C, i, j, 1, 
                                                   int(cost), bound_tracker))
results = ray.get(futures)
```

## Testowanie

Uruchom testy lokalne:
```bash
python test_improvements.py
```

Uruchom testy rozproszone (wymaga klastra Ray):
```bash
python python/run_ray.py
```

## Oczekiwane Wyniki

### Współdzielone Ograniczenie
- **Przyspieszenie:** 1.3-1.5x
- **Główna korzyść:** Zmniejszona ilość sprawdzanych węzłów dzięki lepszemu przycinaniu

### Drobne Zadania
- **Przyspieszenie:** 2-3x (łącznie z współdzielonym ograniczeniem)
- **Główna korzyść:** Znacznie lepsze równoważenie obciążenia

### Razem
- **Oczekiwane przyspieszenie:** 3-5x z 9 węzłami
- **Teoretyczne maksimum:** ~9x (ograniczone przez overhead komunikacji i synchronizacji)

## Dalsze Możliwe Usprawnienia

1. **Work Stealing:** Implementacja dynamicznego kradzenia pracy między workerami
2. **Adaptive Granularity:** Automatyczne dostosowywanie granulacji zadań w zależności od rozmiaru problemu
3. **Early Termination:** Zatrzymanie wszystkich workerów gdy optymalność jest udowodniona
4. **Heurystyka Kolejności:** Inteligentniejsza kolejność rozważania miast dla lepszego przycinania
5. **Okresowe Aktualizacje Ograniczeń:** Workers okresowo sprawdzają i aktualizują ograniczenia podczas długich obliczeń

## Test 6: Wsadowe Podejście Wielowątkowe (NOWE)

### Problem z Testem 5
Test 5 tworzy zbyt wiele zadań: (n-1)×(n-2) = 13×12 = 156 zadań dla n=14. Powoduje to:
- Nadmierne obciążenie komunikacyjne między workerami
- Zbyt dużo czasu poświęconego na planowanie i synchronizację zadań
- Sieć staje się wąskim gardłem w środowiskach rozproszonych

### Rozwiązanie: Zrównoważona Granulacja Zadań
Test 6 implementuje **podejście wsadowe**, które:
- Tworzy pośrednią liczbę zadań (między Testem 4 a Testem 5)
- Każde zadanie przetwarza wiele miast sekwencyjnie
- Automatycznie dostosowuje rozmiar wsadu na podstawie dostępnych workerów

**Implementacja:** `solve_city_batch()` w `python/ray_cvrp.py`

```python
@ray.remote
def solve_city_batch(dist_np, C, cities, BnB, bound_value, bound_tracker=None):
    """
    Przetwarza wiele miast w jednym zadaniu.
    Redukuje obciążenie komunikacyjne przy zachowaniu dobrego równoważenia obciążenia.
    """
    # ... przetwarzaj każde miasto w wsadzie ...
```

### Strategia Obliczania Zadań
- **Cel:** 2-3 zadania na dostępnego workera
- **Rozmiar wsadu:** `liczba_miast / (liczba_workerów × 2.5)`
- **Przykład:** Dla n=14, 4 workery → ~10 zadań zamiast 156

### Tabela Porównawcza

| Test | Zadania dla n=14 | Komunikacja | Równoważenie | Najlepsze dla |
|------|------------------|-------------|--------------|---------------|
| Test 4 | 13 | Niska | Słabe | Małe klastry |
| Test 6 (NOWY) | ~10-20 | Średnia | Dobre | Większość scenariuszy |
| Test 5 | 156 | Wysoka | Doskonałe | Szybkie sieci |

### Korzyści
1. **Zredukowana Komunikacja:** 10-15x mniej zadań niż Test 5
2. **Lepsze niż Test 4:** Zapewnia dobre równoważenie obciążenia
3. **Adaptacyjne:** Skaluje się z dostępnymi workerami
4. **Optymalne dla Rozproszonego:** Zaprojektowane do minimalizacji wąskiego gardła sieciowego

### Oczekiwana Wydajność
- **Przyspieszenie vs Test 5:** 1.2-1.5x na rozproszonych klastrach (dzięki mniejszej komunikacji)
- **Przyspieszenie vs Test 4:** 1.3-1.8x (dzięki lepszemu równoważeniu obciążenia)
- **Najlepsza ogólna wydajność:** Na wielowęzłowych klastrach z umiarkowaną prędkością sieci

## Kompilacja

Aby przekompilować bibliotekę C++ po zmianach:

```bash
cd cpp
g++ -shared -fPIC -O2 distributed_bnb.cpp -o libcvrp.so
```

## Struktura Plików

```
distributed_sum/
├── cpp/
│   ├── distributed_bnb.cpp    # C++ implementation (dodano solve_from_two_cities)
│   └── libcvrp.so             # Skompilowana biblioteka
├── python/
│   ├── ray_cvrp.py            # Ray workers (dodano BoundTracker, solve_city_pair, solve_city_batch)
│   └── run_ray.py             # Główny skrypt testowy (dodano testy porównawcze wraz z Testem 6)
└── test_improvements.py       # Lokalne testy jednostkowe
```

## Podsumowanie

Te usprawnienia rozwiązują problem słabego skalowania w oryginalnej implementacji poprzez:

1. **Współdzielenie informacji** między workerami (BoundTracker)
2. **Lepsze rozłożenie pracy** (drobniejsze zadania)
3. **Dynamiczną aktualizację** ograniczeń podczas wykonywania
4. **Zrównoważoną granulację zadań** (Test 6 - optymalne dla obliczeń rozproszonych)

Oczekujemy, że te zmiany zwiększą przyspieszenie z ~1.7x do ~3-5x z 9 węzłami, co jest znacznie bliższe idealnemu skalowaniu.
