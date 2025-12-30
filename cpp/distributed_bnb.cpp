#include <iostream>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <vector>
#include <algorithm>
#include <omp.h>

using namespace std;
class CVRP_BnB;

// ===========================
// 1. Generowanie danych
// ===========================
void load_coordinates(double** coords, int n) {
    for (int i = 0; i < n; i++) {
        coords[i][0] = rand() % 10001;
        coords[i][1] = rand() % 10001;
    }
}

// ===========================
// 2. Macierz odleg�o�ci
// ===========================
double euclidean(double* p1, double* p2) {
    return sqrt((p1[0] - p2[0]) * (p1[0] - p2[0]) +
        (p1[1] - p2[1]) * (p1[1] - p2[1]));
}

void distance_matrix(double** coords, double** dist, int n) {
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            if (i != j)
                dist[i][j] = euclidean(coords[i], coords[j]);
            else
                dist[i][j] = 0.0;
        }
    }
}

// ===========================
// 3. Dolne ograniczenie
// ===========================
double lower_bound(double** dist, bool* visited, int n) {
    double lb = 0.0;
    for (int i = 1; i < n; i++) {
        if (!visited[i]) {
            double min_dist = 1e9;
            for (int j = 0; j < n; j++) {
                if (i != j && dist[i][j] < min_dist)
                    min_dist = dist[i][j];
            }
            lb += min_dist;
        }
    }
    return lb;
}

// ===========================
// 4. Branch and Bound � CVRP
// ===========================
class CVRP_BnB {
public:
    double** dist;
    int n;
    int C;
    double best_cost;
    int cut;
    int checks;

    CVRP_BnB(double** dist_matrix, int size, int capacity, int bound_value) {
        dist = dist_matrix;
        n = size;
        C = capacity;
        best_cost = bound_value;
        cut = 0;
        checks = 0;
    }

    void branch_and_bound(int* route, int route_len,
        bool* visited,
        int current_load,
        double current_cost,
        bool cutting) {

        // wszystkie miasta odwiedzone
        bool done = true;
        for (int i = 0; i < n; i++) {
            if (!visited[i]) {
                done = false;
                break;
            }
        }

        if (done) {
            double total_cost = current_cost + dist[route[route_len - 1]][0];
            if (total_cost < best_cost)
                best_cost = total_cost;
            return;
        }

        // lower bound
        double lb = current_cost + lower_bound(dist, visited, n);
        checks++;
        if (lb >= best_cost && cutting) {
            cut++;
            return;
        }

        // dodawanie miast
        for (int i = 1; i < n; i++) {
            if (!visited[i] && current_load + 1 <= C) {
                visited[i] = true;
                route[route_len] = i;

                branch_and_bound(route, route_len + 1,
                    visited,
                    current_load + 1,
                    current_cost + dist[route[route_len - 1]][i],
                    cutting);

                visited[i] = false;
            }
        }

        // nowy pojazd
        if (current_load > 0) {
            int new_route[20];
            new_route[0] = 0;

            branch_and_bound(new_route, 1,
                visited,
                0,
                current_cost,
                cutting);
        }
    }
};
// ===========================
// 4b. Funkcja do rozproszenia (C API)
// ===========================
extern "C" {

    double solve_from_first_city(double** dist, int n, int C, int first_city, int cutting, int bound_value) {
        // Safety check: ensure n doesn't exceed maximum route size
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);

        bool* visited = new bool[n];
        for (int i = 0; i < n; i++) visited[i] = false;

        visited[0] = true;
        visited[first_city] = true;

        int route[20];
        route[0] = 0;
        route[1] = first_city;

        solver.branch_and_bound(
            route,
            2,
            visited,
            1,
            dist[0][first_city],
            cutting!=0
        );

        double result = solver.best_cost;
        delete[] visited;
        return result;
    }

    double solve_from_two_cities(double** dist, int n, int C, int first_city, int second_city, int cutting, int bound_value) {
        // Safety check: ensure n doesn't exceed maximum route size
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);

        bool* visited = new bool[n];
        for (int i = 0; i < n; i++) visited[i] = false;

        visited[0] = true;
        visited[first_city] = true;
        visited[second_city] = true;

        int route[20];
        route[0] = 0;
        route[1] = first_city;
        route[2] = second_city;

        solver.branch_and_bound(
            route,
            3,
            visited,
            2,
            dist[0][first_city] + dist[first_city][second_city],
            cutting!=0
        );

        double result = solver.best_cost;
        delete[] visited;
        return result;
    }

    // ===========================
    // New: Parallel solver using OpenMP for multithread+cluster performance
    // ===========================
    double solve_parallel_hybrid(double** dist, int n, int C, int* initial_cities, 
                                  int initial_count, int cutting, int bound_value, 
                                  int num_threads) {
        // Safety check: ensure n doesn't exceed maximum route size
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        if (num_threads <= 0) {
            num_threads = omp_get_max_threads();
        }
        omp_set_num_threads(num_threads);
        
        // Shared best cost with atomic updates for thread safety
        double global_best = bound_value;
        
        // Generate work items: all possible next cities from the initial route
        vector<int> next_cities;
        for (int i = 1; i < n; i++) {
            bool already_visited = false;
            for (int j = 0; j < initial_count; j++) {
                if (initial_cities[j] == i) {
                    already_visited = true;
                    break;
                }
            }
            if (!already_visited) {
                next_cities.push_back(i);
            }
        }
        
        // Process next cities in parallel using OpenMP
        #pragma omp parallel
        {
            double thread_best = global_best;
            CVRP_BnB solver(dist, n, C, bound_value);
            
            #pragma omp for schedule(dynamic, 1)
            for (int idx = 0; idx < (int)next_cities.size(); idx++) {
                int next_city = next_cities[idx];
                
                // Create local copies for this thread
                bool* visited = new bool[n];
                for (int i = 0; i < n; i++) visited[i] = false;
                visited[0] = true;
                
                int route[20];
                route[0] = 0;
                
                // Set up initial route
                int route_len = 1;
                double current_cost = 0.0;
                int current_load = 0;
                
                for (int i = 0; i < initial_count; i++) {
                    route[route_len] = initial_cities[i];
                    visited[initial_cities[i]] = true;
                    if (i == 0) {
                        current_cost = dist[0][initial_cities[i]];
                    } else {
                        current_cost += dist[initial_cities[i-1]][initial_cities[i]];
                    }
                    route_len++;
                    current_load++;
                }
                
                // Add next city if capacity allows
                if (current_load < C) {
                    route[route_len] = next_city;
                    visited[next_city] = true;
                    if (route_len > 0) {
                        current_cost += dist[route[route_len-1]][next_city];
                    }
                    route_len++;
                    current_load++;
                    
                    // Update solver with current best from any thread
                    #pragma omp critical
                    {
                        if (global_best < solver.best_cost) {
                            solver.best_cost = global_best;
                        }
                    }
                    
                    solver.branch_and_bound(
                        route,
                        route_len,
                        visited,
                        current_load,
                        current_cost,
                        cutting != 0
                    );
                    
                    // Update global best if this thread found better solution
                    if (solver.best_cost < thread_best) {
                        thread_best = solver.best_cost;
                        #pragma omp critical
                        {
                            if (thread_best < global_best) {
                                global_best = thread_best;
                            }
                        }
                    }
                }
                
                delete[] visited;
            }
        }
        
        return global_best;
    }

} // extern "C"

// ===========================
// 5. Main
// ===========================
int main() {
    srand(time(nullptr));

    int ns[] = { 4,5,6,7,8,9,10,11,12,13,14,15 };

    for (int idx = 0; idx < 12; idx++) {
        int n = ns[idx];

        double** coords = new double* [n];
        double** dist = new double* [n];
        for (int i = 0; i < n; i++) {
            coords[i] = new double[2];
            dist[i] = new double[n];
        }

        load_coordinates(coords, n);
        distance_matrix(coords, dist, n);

        CVRP_BnB solver(dist, n, 5, 1e18);

        bool* visited = new bool[n];
        for (int i = 0; i < n; i++) visited[i] = false;
        visited[0] = true;

        int route[20];
        route[0] = 0;

        clock_t start = clock();
        solver.branch_and_bound(route, 1, visited, 0, 0.0, true);
        double elapsed = double(clock() - start) / CLOCKS_PER_SEC;

        cout << "BnB Computing for: " << n << endl;
        cout << "Best cost: " << solver.best_cost << endl;
        cout << "Time of computing: " << elapsed << endl;
        cout << "Checks: " << solver.checks << " Cuts: " << solver.cut << endl;
        cout << "-----------------------------" << endl;

        delete[] visited;
        for (int i = 0; i < n; i++) {
            delete[] coords[i];
            delete[] dist[i];
        }
        delete[] coords;
        delete[] dist;
    }

    return 0;
}
