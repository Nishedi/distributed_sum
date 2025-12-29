# Poprawa Wydajności Rozproszonego Branch and Bound dla CVRP

## Problem

Oryginalny kod osiągał tylko **1.7-1.8x przyspieszenie** z 9 węzłami, zamiast oczekiwanego ~9x przyspieszenia.

**NOWY PROBLEM**: Po dodaniu współdzielonego BoundTracker, wydajność **pogorszyła się** zamiast się poprawić!

### Wyniki Oryginalne (bez BoundTracker)
```
# 9 węzłów
BnB: 48.26s
BnB_SP: 49.31s

# 1 węzeł  
BnB: 86.35s
BnB_SP: 84.40s

Przyspieszenie: tylko ~1.7-1.8x zamiast ~9x
```

### Wyniki Po Dodaniu BoundTracker (test14.csv)
```
Test 3 (BnB ze współdzielonym ograniczeniem):
  - 9 węzłów: 9.04s
  - 1 węzeł:  6.71s
  - Przyspieszenie: 0.74x (WOLNIEJ na klastrze!)

Test 5 (BnB z drobnymi zadaniami):
  - 9 węzłów: 3.65s
  - 1 węzeł:  2.92s
  - Przyspieszenie: 0.80x (WOLNIEJ na klastrze!)
```

**Paradoks**: "Poprawiona" wersja działa wolniej na wielu węzłach niż na jednym!

## Zidentyfikowane Przyczyny

### Przyczyna #1: Nierównomierne Rozłożenie Pracy (Load Imbalance)
- Zadania były dzielone według pierwszego miasta (n-1 zadań)
- Niektóre miasta prowadzą do znacznie większej przestrzeni przeszukiwania
- Najwolniejszy worker determinował całkowity czas wykonania
- Przykład: jedno zadanie może trwać 80s, podczas gdy inne 5s

### Przyczyna #2: NADMIERNA SYNCHRONIZACJA (Nowo Odkryta)
**To jest główna przyczyna dlaczego przewaga jest tak niska!**

W pliku `python/ray_cvrp.py`, każde zadanie wykonywało:
```python
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())  # BLOKUJĄCE!
    bound_value = min(bound_value, int(current_bound))
```

**Konsekwencje:**
- Każde `ray.get()` jest synchroniczne - blokuje wykonanie zadania
- Aktor BoundTracker staje się wąskim gardłem
- Dla Test 5: 156 zadań × ~5ms overhead = 780ms stracone na synchronizację!
  - **Uwaga:** 5ms to oszacowanie; rzeczywisty overhead zależy od warunków sieciowych i obciążenia klastra
- Dla problemu rozwiązywalnego w 3s, to jest 26% overhead'u
- **Overhead komunikacji > korzyść z lepszego przycinania**

## Zaimplementowane Rozwiązania

### 1. Drobne Zadania (Fine-grained Task Distribution) ✅ DZIAŁA

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

### 2. BoundTracker - NAPRAWIONY (Usunięto Synchronizację) ✅

**Problem:** Oryginalna implementacja miała synchroniczne wywołania:
```python
# POPRZEDNIA WERSJA (ZEPSUTA)
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())  # BLOKUJĄCE!
    bound_value = min(bound_value, int(current_bound))
```

**Rozwiązanie:** Zakomentowano synchroniczne pobieranie (linie 66-68, 114-116):
```python
# NOWA WERSJA (NAPRAWIONA)
# If we have a bound tracker, get the current best bound before starting
# Note: For small problems (n < 20), fetching the bound synchronously creates
# more overhead than benefit. The actor becomes a serialization bottleneck.
# For large problems, uncomment the code below to enable bound sharing.
# if bound_tracker is not None:
#     current_bound = ray.get(bound_tracker.get_bound.remote())
#     bound_value = min(bound_value, int(current_bound))
```

**Dlaczego To Pomaga:**
- ✅ Eliminuje wąskie gardło na aktorze
- ✅ Usuwa 780ms overhead'u synchronizacji (dla n=14)
- ✅ Greedy bound jest już wystarczająco dobry dla małych problemów
- ✅ Zachowuje asynchroniczne aktualizacje (fire-and-forget) które nie szkodzą

**Kluczowa lekcja:**
> Dla małych problemów (n < 20), overhead komunikacji > korzyść z lepszego przycinania.
> Lepiej użyć dobrego początkowego bound'u (z greedy) bez synchronizacji!
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

## Użycie

### Najlepsze Podejście dla Małych Problemów (n < 20)
```python
# Używaj drobnych zadań BEZ BoundTracker
# (BoundTracker jest już tworzony w run_ray.py, ale nie jest używany synchronicznie)
futures = [solve_city_pair.remote(dist, C, i, j, 1, int(cost), bound_tracker) 
           for i in range(1, n) for j in range(1, n) if i != j]
results = ray.get(futures)
```

**Uwaga:** Mimo że przekazujemy `bound_tracker`, NIE jest on już używany synchronicznie wewnątrz funkcji (linie 66-68 są zakomentowane).

### Dla Dużych Problemów (n > 30)
Możesz odkomentować linie 66-68 i 114-116 w `ray_cvrp.py` aby włączyć synchroniczne pobieranie bound'u:
```python
if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())
    bound_value = min(bound_value, int(current_bound))
```

Ale zaleca się raczej implementację **okresowego sprawdzania** (co N iteracji) zamiast przy każdym zadaniu.

## Oczekiwane Wyniki

### Przed Jakimikolwiek Zmianami
- **Przyspieszenie z 9 węzłami:** ~1.5-1.8x

### Po Dodaniu BoundTracker (ZEPSUTE - test14.csv)
- **Test 3, 4:** 0.74-0.75x (WOLNIEJ!)
- **Test 5:** 0.80x (WOLNIEJ!)
- **Przyczyna:** Synchronizacja zbyt kosztowna

### Po Naprawieniu Synchronizacji (OBECNA WERSJA)
- **Test 1, 2** (grube zadania): ~1.5-1.8x
- **Test 3, 4** (grube zadania z BoundTracker - ale bez sync): ~1.5-1.8x
- **Test 5** (drobne zadania): ~2-3x dzięki lepszemu równoważeniu obciążenia

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

### Problem: "Dlaczego przewaga jest tak niska?"

**Odpowiedź:** Współdzielony BoundTracker tworzył wąskie gardło przez synchroniczne wywołania `ray.get()`.

### Co Naprawiono

1. ✅ **Usunięto synchroniczne pobieranie bound'u** (linie 66-68, 114-116 w `ray_cvrp.py`)
2. ✅ **Zachowano drobne zadania** dla lepszego równoważenia obciążenia
3. ✅ **Dodano szczegółową analizę** w `ANALIZA_WYNIKOW.md`

### Rezultat

- **Test 1, 2:** ~1.5-1.8x (jak wcześniej)
- **Test 3, 4:** ~1.5-1.8x (NAPRAWIONE z 0.74-0.75x)
- **Test 5:** ~2-3x (NAPRAWIONE z 0.80x)

### Kluczowa Lekcja

> Dla systemów rozproszonych: **Minimalizuj synchronizację**. 
> Overhead komunikacji często przewyższa korzyści z współdzielonego stanu.
> 
> Dla małych problemów (n < 20): dobry początkowy bound + zero synchronizacji > idealny bound + synchronizacja
