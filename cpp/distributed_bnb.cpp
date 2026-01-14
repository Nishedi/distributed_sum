#include <iostream>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <chrono>
using namespace std;
typedef double (*BoundCallback)(double);
class CVRP_BnB;

void load_coordinates(double** coords, int n) {
    for (int i = 0; i < n; i++) {
        coords[i][0] = rand() % 10001;
        coords[i][1] = rand() % 10001;
    }
}

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

class CVRP_BnB {
public:
    double** dist;
    int n;
    int C;
    double best_cost;
    int cut;
    int checks;

    BoundCallback callback;
    std::chrono::steady_clock::time_point last_sync_time;
    int sync_interval_iters;
    int sync_interval_ms;

    CVRP_BnB(double** dist_matrix, int size, int capacity, int bound_value, BoundCallback cb) {
        dist = dist_matrix;
        n = size;
        C = capacity;
        best_cost = bound_value;
        cut = 0;
        checks = 0;

        callback = cb;
        last_sync_time = std::chrono::steady_clock::now();
        sync_interval_iters = 1000; // Check time every 1000 nodes
        sync_interval_ms = 200;     // Sync with host every 200ms
    }

    void branch_and_bound(int* route, int route_len,
        bool* visited,
        int current_load,
        double current_cost,
        bool cutting) {

        if (callback != nullptr) {
            // Only check clock every X iterations to save performance
            if (checks % sync_interval_iters == 0) {
                auto now = std::chrono::steady_clock::now();
                auto elapsed = std::chrono::duration_cast<std::chrono::milliseconds>(now - last_sync_time).count();

                // If enough time passed, call Python!
                if (elapsed > sync_interval_ms) {
                    // Send our local best, get back global best
                    double global_best = callback(best_cost);

                    // Update local if global is better
                    if (global_best < best_cost) {
                        best_cost = global_best;
                    }
                    last_sync_time = now;
                }
            }
        }

        bool done = true;
        for (int i = 0; i < n; i++) {
            if (!visited[i]) {
                done = false;
                break;
            }
        }

        if (done) {
            double total_cost = current_cost + dist[route[route_len - 1]][0];
            if (total_cost < best_cost) {
                best_cost = total_cost;
                // Immediate update if we found a solution
                if (callback != nullptr) {
                     callback(best_cost);
                }
            }
            return;
        }

        double lb = current_cost + lower_bound(dist, visited, n);
        checks++;
        if (lb >= best_cost && cutting) {
            cut++;
            return;
        }

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

extern "C" {
    double solve_generic(double** dist, int n, int C, int* start_route, int route_len, bool* visited, int load, double current_cost, int cutting, int bound_value, BoundCallback cb) {
        if (n > 20) return 1e18;

        CVRP_BnB solver(dist, n, C, bound_value, cb);

        solver.branch_and_bound(
            start_route,
            route_len,
            visited,
            load,
            current_cost,
            cutting != 0
        );

        return solver.best_cost;
    }
    double solve_from_first_city(double** dist, int n, int C, int first_city, int cutting, int bound_value) {
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
    double solve_with_callback(double** c_mat, int n, int C, int city, int cutting, int bound_value, BoundCallback cb) {
         CVRP_BnB solver(c_mat, n, C, bound_value, cb);

        bool* visited = new bool[n];
        for (int i = 0; i < n; i++) visited[i] = false;

        visited[0] = true;
        visited[city] = true;

        int route[20];
        route[0] = 0;
        route[1] = city;

        solver.branch_and_bound(
            route,
            2,
            visited,
            1,
            c_mat[0][city],
            cutting!=0
        );

        double result = solver.best_cost;
        delete[] visited;
        return result;
    }

} // extern "C"

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
