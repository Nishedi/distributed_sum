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
│   ├── ray_cvrp.py            # Ray workers (dodano BoundTracker, solve_city_pair)
│   └── run_ray.py             # Główny skrypt testowy (dodano testy porównawcze)
└── test_improvements.py       # Lokalne testy jednostkowe
```

## Podsumowanie

Te usprawnienia rozwiązują problem słabego skalowania w oryginalnej implementacji poprzez:

1. **Współdzielenie informacji** między workerami (BoundTracker)
2. **Lepsze rozłożenie pracy** (drobniejsze zadania)
3. **Dynamiczną aktualizację** ograniczeń podczas wykonywania

Oczekujemy, że te zmiany zwiększą przyspieszenie z ~1.7x do ~3-5x z 9 węzłami, co jest znacznie bliższe idealnemu skalowaniu.
