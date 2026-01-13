#include <iostream>
#include <cmath>
#include <cstdlib>
#include <ctime>
#include <chrono>

using namespace std;
class CVRP_BnB;

// Callback type for querying bound from host
typedef double (*BoundQueryCallback)(void* user_data);

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
    
    // Synchronization parameters
    BoundQueryCallback bound_callback;
    void* callback_user_data;
    int sync_check_interval;  // Minimum iterations between sync checks
    double sync_time_interval;  // Minimum seconds between sync checks
    int iterations_since_sync;
    chrono::steady_clock::time_point last_sync_time;
    int sync_count;  // Track number of synchronizations performed

    CVRP_BnB(double** dist_matrix, int size, int capacity, int bound_value) {
        dist = dist_matrix;
        n = size;
        C = capacity;
        best_cost = bound_value;
        cut = 0;
        checks = 0;
        bound_callback = nullptr;
        callback_user_data = nullptr;
        sync_check_interval = 10000;  // Default: check every 10000 iterations
        sync_time_interval = 1.0;      // Default: check every 1 second
        iterations_since_sync = 0;
        last_sync_time = chrono::steady_clock::now();
        sync_count = 0;
    }
    
    void set_bound_callback(BoundQueryCallback callback, void* user_data, int check_interval = 10000, double time_interval = 1.0) {
        bound_callback = callback;
        callback_user_data = user_data;
        sync_check_interval = check_interval;
        sync_time_interval = time_interval;
    }
    
    void check_and_sync_bound() {
        if (bound_callback == nullptr) {
            return;
        }
        
        iterations_since_sync++;
        
        // Check if enough iterations have passed
        if (iterations_since_sync <= sync_check_interval) {
            return;
        }
        
        // Check if enough time has passed
        auto now = chrono::steady_clock::now();
        chrono::duration<double> elapsed = now - last_sync_time;
        if (elapsed.count() <= sync_time_interval) {
            return;
        }
        
        // Perform synchronization: query bound from host
        double host_bound = bound_callback(callback_user_data);
        
        // Update local bound if host has a better one
        if (host_bound < best_cost) {
            best_cost = host_bound;
        }
        
        // Reset counters
        iterations_since_sync = 0;
        last_sync_time = now;
        sync_count++;
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
            if (total_cost < best_cost)
                best_cost = total_cost;
            return;
        }

        double lb = current_cost + lower_bound(dist, visited, n);
        checks++;
        
        // Periodically check and synchronize bound with host
        check_and_sync_bound();
        
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

    // New version with callback support
    double solve_from_first_city_with_callback(double** dist, int n, int C, int first_city, int cutting, int bound_value, 
                                                 BoundQueryCallback callback, void* user_data,
                                                 int sync_interval, double time_interval) {
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);
        
        // Set up callback if provided
        if (callback != nullptr) {
            solver.set_bound_callback(callback, user_data, sync_interval, time_interval);
        }

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

    // Original version without callback (for backward compatibility)
    double solve_from_first_city(double** dist, int n, int C, int first_city, int cutting, int bound_value) {
        return solve_from_first_city_with_callback(dist, n, C, first_city, cutting, bound_value, nullptr, nullptr, 10000, 1.0);
    }

    // New version with callback support
    double solve_from_two_cities_with_callback(double** dist, int n, int C, int first_city, int second_city, int cutting, int bound_value,
                                                 BoundQueryCallback callback, void* user_data,
                                                 int sync_interval, double time_interval) {
        if (n > 20) {
            cerr << "Error: Number of cities exceeds maximum supported (20)" << endl;
            return 1e18;
        }
        
        CVRP_BnB solver(dist, n, C, bound_value);
        
        // Set up callback if provided
        if (callback != nullptr) {
            solver.set_bound_callback(callback, user_data, sync_interval, time_interval);
        }

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

    // Original version without callback (for backward compatibility)
    double solve_from_two_cities(double** dist, int n, int C, int first_city, int second_city, int cutting, int bound_value) {
        return solve_from_two_cities_with_callback(dist, n, C, first_city, second_city, cutting, bound_value, nullptr, nullptr, 10000, 1.0);
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
