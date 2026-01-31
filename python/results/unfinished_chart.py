import glob
import re
import pandas as pd
import matplotlib.pyplot as plt


def analyze_unfinished_vs_load():
    # Szukamy wszystkich plików wyników
    files = glob.glob("sim_results_*_*_Seed*tph.csv")

    results = []

    print(f"Znaleziono plików: {len(files)}")

    for filename in files:
        # Dopasowanie nazwy pliku: sim_results_A_30_Seed1tph.csv
        match = re.search(r"sim_results_([AB])_(\d+)_Seed(\d+)_hardtph\.csv", filename)

        if match:
            mode = match.group(1)
            tph = int(match.group(2))
            # seed = int(match.group(3))

            try:
                df = pd.read_csv(filename)

                # Liczymy zadania niedokończone (UNFINISHED, IGNORED lub cokolwiek innego niż COMPLETED)
                unfinished_count = len(df[df['status'] != 'COMPLETED'])

                # Alternatywnie: jeśli chcesz liczyć tylko te, które weszły ale nie skończyły:
                # unfinished_count = len(df[df['status'] == 'UNFINISHED'])

                # Zapisujemy wynik dla tego konkretnego pliku (Seeda)
                results.append({
                    "Mode": mode,
                    "TPH": tph,
                    "Unfinished_Count": unfinished_count
                })
            except Exception as e:
                print(f"Błąd przy odczycie {filename}: {e}")

    # Tworzymy DataFrame z wyników
    res_df = pd.DataFrame(results)

    if res_df.empty:
        print("Brak danych do wyrysowania.")
        return

    # Agregacja: Liczymy średnią liczbę niedokończonych zadań dla każdego Mode i TPH (uśredniamy Seedy)
    agg_df = res_df.groupby(['Mode', 'TPH'], as_index=False)['Unfinished_Count'].mean()
    agg_df = agg_df.sort_values(by=['Mode', 'TPH'])

    print("\nŚrednia liczba niedokończonych zadań:")
    print(agg_df)

    # --- RYSOWANIE WYKRESU ---
    plt.figure(figsize=(10, 6))

    # Seria dla Mode A
    data_a = agg_df[agg_df['Mode'] == 'A']
    if not data_a.empty:
        plt.plot(data_a['TPH'], data_a['Unfinished_Count'],
                 marker='o', linestyle='-', color='red', label='Mode A (Cluster)')

    # Seria dla Mode B
    data_b = agg_df[agg_df['Mode'] == 'B']
    if not data_b.empty:
        plt.plot(data_b['TPH'], data_b['Unfinished_Count'],
                 marker='s', linestyle='--', color='blue', label='Mode B (Node Parallel)')

    plt.xlabel('Obciążenie (Zadania/h)')
    plt.ylabel('Średnia liczba niedokończonych zadań')
    plt.title('Niewydolność systemu: Liczba zadań odrzuconych/nieukończonych vs Obciążenie')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.legend()

    output_filename = '../fig/wykres_unfinished_vs_n_hard.png'
    plt.savefig(output_filename)
    print(f"\nWykres zapisano jako: {output_filename}")
    # plt.show()


if __name__ == "__main__":
    analyze_unfinished_vs_load()