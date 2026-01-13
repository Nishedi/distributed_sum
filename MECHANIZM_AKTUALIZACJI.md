# Mechanizm Aktualizacji Najlepszego Rozwiązania - Odpowiedź na Pytanie

## Pytanie
Jak działa mechanizm aktualizacji najlepszego rozwiązania w trakcie pracy? Po znalezieniu upperbounda od razu wysyła do hosta informacje czy dopiero po zakończeniu? Jak inne workery odbierają tą informacje tylko na początku czy już w trakcie?

## Odpowiedź

### Jak działa mechanizm PRZED zmianami

1. **Na początku zadania:**
   - Worker pobiera aktualne najlepsze ograniczenie z BoundTracker
   - Worker otrzymuje stałą wartość bound jako parametr do C++

2. **Podczas wykonywania w C++:**
   - C++ używa stałej wartości bound przekazanej na początku
   - BRAK możliwości aktualizacji bound podczas obliczeń
   - Worker nie może skorzystać z lepszych rozwiązań znalezionych przez siebie

3. **Po zakończeniu zadania:**
   - Worker wysyła swój najlepszy wynik do BoundTracker (fire-and-forget)
   - BoundTracker aktualizuje globalne ograniczenie jeśli nowy wynik jest lepszy

### Jak działa mechanizm PO zmianach (obecna implementacja)

1. **Na początku zadania:**
   - Worker pobiera aktualne najlepsze ograniczenie z BoundTracker: `ray.get(bound_tracker.get_bound.remote())`
   - Worker tworzy lokalny `shared_bound` jako `ctypes.c_double` i przekazuje go przez referencję do C++
   - Wartość startowa to minimum z: parametru bound_value i aktualnego BoundTracker

2. **Podczas wykonywania w C++:**
   - Algorytm sprawdza `shared_bound` co 1000 iteracji w funkcji `branch_and_bound()`
   - Jeśli worker znajdzie lepsze rozwiązanie lokalnie, natychmiast aktualizuje `shared_bound`
   - C++ może szybciej przyciąć gałęzie używając zaktualizowanego bound
   - **WAŻNE:** To jest lokalna kopia dla tego workera - inne workery NIE widzą tych zmian podczas ich pracy

3. **Po zakończeniu zadania:**
   - Worker wysyła najlepszy wynik do BoundTracker: `bound_tracker.update_bound.remote(result)`
   - Aktualizacja jest asynchroniczna (fire-and-forget)
   - C++ również aktualizuje `shared_bound` przed zwróceniem wyniku (dla spójności)

### Kiedy inne workery otrzymują informacje o lepszym rozwiązaniu?

**TYLKO NA POCZĄTKU** - inne workery pobierają zaktualizowany bound z BoundTracker gdy:
- Rozpoczynają nowe zadanie
- Wywołują `ray.get(bound_tracker.get_bound.remote())`

Workery **NIE otrzymują** aktualizacji podczas trwania swoich obliczeń, ponieważ:
- Workery mogą działać na różnych maszynach w klastrze
- Aktywne odpytywanie BoundTracker z C++ podczas obliczeń byłoby zbyt kosztowne
- Callback z C++ do Pythona w ciasnych pętlach miałby ogromny overhead

### Dlaczego to działa efektywnie?

1. **Dobre początkowe ograniczenie:**
   - Algorytm zachłanny (greedy) dostarcza rozsądny starting point
   - Workery rozpoczynające się później korzystają z wyników wcześniejszych workerów

2. **Lokalne aktualizacje w ramach workera:**
   - Worker może używać swoich własnych ulepszeń bound
   - Znacznie lepsza efektywność niż stała wartość bound

3. **Więcej małych zadań = częstsze aktualizacje:**
   - Test 5 (pary miast) tworzy więcej zadań niż Test 3 (pojedyncze miasta)
   - Więcej punktów pobierania zaktualizowanego bound z BoundTracker
   - Lepsze balansowanie obciążenia + częstsze aktualizacje

### Wpływ na wydajność (z dokumentacji)

Z testów na 16 miastach:
- **Test 1 (bez współdzielenia):** 2598.95s
- **Test 3 (ze współdzieleniem):** 607.79s (4.3x szybciej)
- **Test 5 (pary + współdzielenie):** 432.38s (6x szybciej)

### Zmiany w kodzie

#### C++ (distributed_bnb.cpp):
```cpp
// Dodano pole w klasie CVRP_BnB
double* shared_bound;  // Wskaźnik do współdzielonej wartości bound
int check_interval;    // Sprawdź co N iteracji

// W funkcji branch_and_bound() dodano:
if (shared_bound != nullptr && checks % check_interval == 0) {
    if (*shared_bound < best_cost) {
        best_cost = *shared_bound;
    }
}

// Funkcje extern "C" przyjmują teraz shared_bound:
double solve_from_first_city(..., double* shared_bound)
double solve_from_two_cities(..., double* shared_bound)
```

#### Python (ray_cvrp.py):
```python
# Utworzenie lokalnego shared_bound
shared_bound = ctypes.c_double(bound_value)

if bound_tracker is not None:
    current_bound = ray.get(bound_tracker.get_bound.remote())
    shared_bound.value = min(bound_value, current_bound)

# Przekazanie przez referencję
result = lib.solve_from_first_city(..., ctypes.byref(shared_bound))
```

## Podsumowanie

**Odpowiedź na pytanie:**
- Po znalezieniu upperbound, worker **od razu aktualizuje swój lokalny shared_bound** (dla własnego użytku)
- Worker wysyła informację do BoundTracker **dopiero po zakończeniu** (asynchronicznie)
- Inne workery odbierają informację **tylko na początku nowego zadania**
- **NIE** ma aktywnych aktualizacji podczas trwania obliczeń w innych workerach

To jest kompromis między:
- Ideałem (ciągłe aktualizacje między wszystkimi workerami)
- Rzeczywistością (overhead komunikacji byłby większy niż korzyść)

System jest efektywny dzięki:
✓ Dobremu początkowemu bound (greedy)
✓ Lokalnym aktualizacjom w każdym workerze
✓ Szybkiej propagacji między zadaniami
✓ Więcej małych zadań = częstsze punkty synchronizacji
