import sys
import os
import csv

def main():
    if len(sys.argv) != 2:
        print("Użycie: python sort_results.py <plik.csv>")
        sys.exit(1)

    input_file = sys.argv[1]

    base, ext = os.path.splitext(input_file)
    output_file = f"{base}_sorted{ext}"

    rows = []
    header = None

    with open(input_file, newline='', encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            if not row:
                continue

            # wykrycie nagłówka (powtarza się w pliku)
            if row[0] == "n" and "method" in row:
                if header is None:
                    header = row
                continue

            rows.append(row)

    if header is None:
        print("Błąd: nie znaleziono nagłówka CSV")
        sys.exit(1)

    # indeks kolumny "method"
    method_idx = header.index("method")

    # sortowanie po method
    rows.sort(key=lambda r: r[method_idx])

    with open(output_file, "w", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"Zapisano posortowany plik: {output_file}")

if __name__ == "__main__":
    main()
