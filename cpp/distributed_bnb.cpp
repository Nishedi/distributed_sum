#include <iostream>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <chrono>

using namespace std;
using namespace std::chrono;

// Callback type for querying the current bound from host
typedef double (*GetBoundCallback)(void* context);
// Callback type for updating the bound on host
typedef void (*UpdateBoundCallback)(void* context, double new_bound);

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
    
    // Callback support for synchronous bound updates
    GetBoundCallback get_bound_callback;
    UpdateBoundCallback update_bound_callback;
    void* callback_context;
    
    // Throttling parameters
    int sync_check_interval;      // Number of iterations between sync checks
    double sync_time_interval_ms; // Minimum time (ms) between sync checks
    int iterations_since_sync;
    steady_clock::time_point last_sync_time;
    double last_synced_bound;

    CVRP_BnB(double** dist_matrix, int size, int capacity, int bound_value) {
        dist = dist_matrix;
        n = size;
        C = capacity;
        best_cost = bound_value;
        cut = 0;
        checks = 0;
        
        // Initialize callback pointers to nullptr (no callbacks by default)
        get_bound_callback = nullptr;
        update_bound_callback = nullptr;
        callback_context = nullptr;
        
        // Default throttling parameters
        sync_check_interval = 1000;     // Check every 1000 iterations
        sync_time_interval_ms = 100.0;  // At least 100ms between syncs
        iterations_since_sync = 0;
        last_sync_time = steady_clock::now();
        last_synced_bound = bound_value;
    }

    void set_callbacks(GetBoundCallback get_cb, UpdateBoundCallback update_cb, void* context,
                      int check_interval = 1000, double time_interval_ms = 100.0) {
        get_bound_callback = get_cb;
        update_bound_callback = update_cb;
        callback_context = context;
        sync_check_interval = check_interval;
        sync_time_interval_ms = time_interval_ms;
    }

    void synchronize_bound() {
        if (get_bound_callback == nullptr || update_bound_callback == nullptr) {
            return; // No callbacks set, skip synchronization
        }
        
        // Check if we should synchronize (throttling)
        iterations_since_sync++;
        auto now = steady_clock::now();
        auto time_since_sync = duration_cast<milliseconds>(now - last_sync_time).count();
        
        bool should_sync = (iterations_since_sync >= sync_check_interval) || 
                          (time_since_sync >= sync_time_interval_ms && best_cost < last_synced_bound);
        
        if (should_sync) {
            // Get current bound from host
            double host_bound = get_bound_callback(callback_context);
            
            // Update our bound if host has better
            if (host_bound < best_cost) {
                best_cost = host_bound;
            }
            
            // Send our bound to host if we have better
            if (best_cost < host_bound) {
                update_bound_callback(callback_context, best_cost);
            }
            
            // Reset throttling counters
            iterations_since_sync = 0;
            last_sync_time = now;
            last_synced_bound = best_cost;
        }
    }

    void branch_and_bound(int* route, int route_len,
        bool* visited,
        int current_load,
        double current_cost,
        bool cutting) {

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
                // Synchronize when we find a better solution
                if (update_bound_callback != nullptr) {
                    update_bound_callback(callback_context, best_cost);
                    last_synced_bound = best_cost;
                }
            }
            return;
        }

        double lb = current_cost + lower_bound(dist, visited, n);
        checks++;
        
        // Periodically synchronize bound with host
        synchronize_bound();
        
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

    // New function with callback support for synchronous bound updates
    double solve_from_first_city_with_sync(double** dist, int n, int C, int first_city, int cutting, int bound_value,
                                          GetBoundCallback get_bound_cb, UpdateBoundCallback update_bound_cb, void* context,
                                          int sync_check_interval, double sync_time_interval_ms) {
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);
        
        // Set up callbacks for synchronous bound updates
        solver.set_callbacks(get_bound_cb, update_bound_cb, context, sync_check_interval, sync_time_interval_ms);

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

    // New function with callback support for city pairs
    double solve_from_two_cities_with_sync(double** dist, int n, int C, int first_city, int second_city, int cutting, int bound_value,
                                          GetBoundCallback get_bound_cb, UpdateBoundCallback update_bound_cb, void* context,
                                          int sync_check_interval, double sync_time_interval_ms) {
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);
        
        // Set up callbacks for synchronous bound updates
        solver.set_callbacks(get_bound_cb, update_bound_cb, context, sync_check_interval, sync_time_interval_ms);

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
