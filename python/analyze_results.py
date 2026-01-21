import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import argparse
import os
import numpy as np

sns.set_theme(style="whitegrid", context="paper", font_scale=1.2)
plt.rcParams['figure.figsize'] = (10, 6)
plt.rcParams['savefig.dpi'] = 300


def load_data(filenames):
    dfs = []
    for fn in filenames:
        if os.path.exists(fn):
            try:
                df = pd.read_csv(fn)
                dfs.append(df)
            except Exception as e:
                print(f"Błąd przy wczytywaniu {fn}: {e}")
        else:
            print(f"Plik nie istnieje: {fn}")

    if not dfs:
        return None
    return pd.concat(dfs, ignore_index=True)


def print_statistical_summary(df):
    print("\n" + "=" * 80)
    print(" SZCZEGÓŁOWY RAPORT STATYSTYCZNY (HPC CVRP SCHEDULING)")
    print("=" * 80)

    grouped = df.groupby(['scenario', 'method'])

    makespan = grouped.apply(lambda x: x['finish_ts'].max() - x['arrival_ts'].min())

    print("\n--- [1] MAKESPAN (Całkowity czas przetworzenia partii) ---")
    print(makespan.to_string())

    metrics = ['wait_time', 'service_time', 'turnaround_time']

    print("\n--- [2] METRYKI ZADAŃ (Średnia ± Odchylenie Std) ---")
    stats = grouped[metrics].agg(['mean', 'std', 'min', 'max'])

    print(stats.round(4).to_string())

    print("\n" + "=" * 80)


def plot_turnaround_time(df, output_dir):
    plt.figure()

    ax = sns.barplot(
        data=df,
        x='scenario',
        y='turnaround_time',
        hue='method',
        palette="viridis",
        errorbar='sd',
        capsize=.1
    )

    plt.title('Average Turnaround Time by Scenario (Lower is Better)')
    plt.ylabel('Time (s)')
    plt.xlabel('Scenario')
    plt.legend(title='Scheduling Strategy')

    filename = os.path.join(output_dir, "plot_turnaround_time.png")
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Zapisano wykres: {filename}")
    plt.close()


def plot_wait_time_distribution(df, output_dir):
    plt.figure()

    sns.boxplot(
        data=df,
        x='scenario',
        y='wait_time',
        hue='method',
        palette="Set2"
    )

    plt.title('Wait Time Distribution (Impact of Queue Blocking)')
    plt.ylabel('Wait Time (s)')
    plt.xlabel('Scenario')
    plt.legend(title='Scheduling Strategy')

    filename = os.path.join(output_dir, "plot_wait_time_dist.png")
    plt.tight_layout()
    plt.savefig(filename)
    print(f"Zapisano wykres: {filename}")
    plt.close()


def plot_latency_vs_throughput_scatter(df, output_dir):
    g = sns.FacetGrid(df, col="scenario", hue="method", height=5, aspect=1, palette="deep")
    g.map(sns.scatterplot, "service_time", "wait_time", s=100, alpha=0.7)

    g.add_legend()
    g.set_axis_labels("Service Time (Compute Cost)", "Wait Time (Queue Cost)")
    g.fig.suptitle("Trade-off: Compute Speed vs Queueing Delay", y=1.02)

    filename = os.path.join(output_dir, "plot_tradeoff_scatter.png")
    plt.savefig(filename)
    print(f"Zapisano wykres: {filename}")
    plt.close()


def plot_timeline_gantt(df, output_dir):
    scenarios = df['scenario'].unique()

    for sc in scenarios:
        subset = df[df['scenario'] == sc].copy()
        subset = subset.sort_values(by=['method', 'start_ts'])

        plt.figure(figsize=(12, 6))

        methods = subset['method'].unique()
        colors = sns.color_palette("husl", len(methods))
        method_color_map = dict(zip(methods, colors))

        for _, row in subset.iterrows():
            plt.hlines(
                y=f"{row['method']} - Task {row['task_id']}",
                xmin=row['start_ts'],
                xmax=row['finish_ts'],
                linewidth=5,
                color=method_color_map[row['method']],
                alpha=0.8
            )
            plt.plot(row['arrival_ts'], f"{row['method']} - Task {row['task_id']}", 'k|', markersize=10)

        plt.title(f'Task Execution Timeline - Scenario: {sc}')
        plt.xlabel('Simulation Time (s)')
        plt.ylabel('Task Assignment')
        plt.grid(True, axis='x', linestyle='--', alpha=0.5)

        if len(subset) > 20:
            plt.yticks([])

        plt.tight_layout()
        filename = os.path.join(output_dir, f"plot_timeline_{sc}.png")
        plt.savefig(filename)
        print(f"Zapisano wykres: {filename}")
        plt.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analiza wyników symulacji HPC CVRP")
    parser.add_argument("files", nargs='+',
                        help="Lista plików CSV z wynikami (np. results_steady.csv results_burst.csv)")
    parser.add_argument("--out_dir", type=str, default=".", help="Folder na wykresy")

    args = parser.parse_args()

    df = load_data(args.files)

    if df is not None:
        cols = ['arrival_ts', 'start_ts', 'finish_ts', 'wait_time', 'service_time', 'turnaround_time']
        for c in cols:
            df[c] = pd.to_numeric(df[c])

        print_statistical_summary(df)

        plot_turnaround_time(df, args.out_dir)
        plot_wait_time_distribution(df, args.out_dir)
        plot_latency_vs_throughput_scatter(df, args.out_dir)
        plot_timeline_gantt(df, args.out_dir)

        print("\nAnaliza zakończona. Sprawdź pliki PNG.")
    else:
        print("Nie udało się wczytać danych.")