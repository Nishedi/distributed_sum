import math
import random
import time


# ===========================
# 1. Wczytywanie lub generowanie danych
# ===========================
def load_coordinates(filename=None, n=10):
    if filename:
        coords = []
        with open(filename, "r") as f:
            for line in f:
                x, y = map(float, line.strip().split(","))
                coords.append((x, y))
        return coords
    else:
        return [(random.randint(0, 100), random.randint(0, 100)) for _ in range(n)]

# ===========================
# 2. Macierz odległości
# ===========================
def euclidean(p1, p2):
    return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)

def distance_matrix(coords):
    n = len(coords)
    dist = [[0]*n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            if i != j:
                dist[i][j] = euclidean(coords[i], coords[j])
    return dist

# ===========================
# 3. Dolne ograniczenie kosztu (lower bound)
# ===========================
def precompute_min_edges(dist):
    """Precompute minimum outgoing edge for each city"""
    n = len(dist)
    min_edges = [0] * n
    for i in range(n):
        min_edges[i] = min(dist[i][j] for j in range(n) if i != j)
    return min_edges

def lower_bound(dist, visited, min_edges, last_city):
    """
    Improved lower bound:
    1. Sum of minimum edges for unvisited cities
    2. Minimum cost to return to depot from last city
    """
    lb = 0
    n = len(dist)
    
    # Add minimum outgoing edges for unvisited cities
    for i in range(1, n):
        if not visited[i]:
            lb += min_edges[i]
    
    # Add estimated cost to return to depot
    # (minimum distance from any unvisited city to depot)
    if not all(visited):
        min_to_depot = min(dist[i][0] for i in range(1, n) if not visited[i])
        lb += min_to_depot
    
    return lb

# ===========================
# 3b. Greedy heuristic for initial solution
# ===========================
def greedy_initial_solution(dist, capacity):
    """
    Generate a good initial solution using nearest neighbor heuristic
    This provides a better upper bound to start with
    """
    n = len(dist)
    visited = [False] * n
    visited[0] = True
    routes = []
    total_cost = 0
    
    while not all(visited):
        route = [0]
        current_load = 0
        current = 0
        
        while current_load < capacity:
            # Find nearest unvisited city
            min_dist = float('inf')
            next_city = -1
            for i in range(1, n):
                if not visited[i] and dist[current][i] < min_dist:
                    min_dist = dist[current][i]
                    next_city = i
            
            if next_city == -1:
                break
            
            route.append(next_city)
            total_cost += dist[current][next_city]
            visited[next_city] = True
            current = next_city
            current_load += 1
        
        # Return to depot
        total_cost += dist[current][0]
        route.append(0)
        routes.append(route)
    
    return total_cost, routes

# ===========================
# 4. Branch and Bound dla wielopojezdżcowego CVRP
# ===========================
class CVRP_BnB:
    def __init__(self, dist_matrix, capacity, use_greedy_init=True):
        self.dist = dist_matrix
        self.n = len(dist_matrix)
        self.C = capacity
        # Precompute minimum edges for faster lower bound calculation
        self.min_edges = precompute_min_edges(dist_matrix)
        
        # Use greedy heuristic for initial upper bound
        if use_greedy_init:
            self.best_cost, self.best_routes = greedy_initial_solution(dist_matrix, capacity)
        else:
            self.best_cost = float('inf')
            self.best_routes = []
        
        self.cut = 0
        self.checks = 0

    def branch_and_bound(self, route=None, visited=None, current_load=0, current_cost=0, routes=None, cutting = True):
        if route is None:
            route = [0]
        if visited is None:
            visited = [False]*self.n
            visited[0] = True
        if routes is None:
            routes = []

        # Jeśli wszystkie miasta odwiedzone -> zakończenie
        if all(visited):
            total_cost = current_cost + self.dist[route[-1]][0]
            all_routes = routes + [route + [0]]
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_routes = all_routes
            return

        # Cięcie gałęzi za pomocą dolnego ograniczenia
        lb = current_cost + lower_bound(self.dist, visited, self.min_edges, route[-1])
        self.checks += 1
        if lb >= self.best_cost and cutting:
            self.cut+=1
            return

        # Rozważanie kolejnych miast - sortuj według odległości (najbliższe pierwsze)
        # to zwiększa szansę na szybsze znalezienie dobrych rozwiązań
        candidates = []
        for i in range(1, self.n):
            if not visited[i]:
                if current_load + 1 <= self.C:
                    candidates.append((self.dist[route[-1]][i], i))
        
        # Sortuj według odległości
        candidates.sort()
        
        for _, i in candidates:
            visited[i] = True
            self.branch_and_bound(route + [i], visited, current_load + 1,
                                  current_cost + self.dist[route[-1]][i], routes, cutting)
            visited[i] = False

        # Rozpoczęcie nowej trasy pojazdu, jeśli bieżąca nie może zabrać więcej
        if current_load > 0:
            self.branch_and_bound([0], visited, 0, current_cost, routes + [route], cutting)

# ===========================
# 5. Uruchomienie skryptu
# ===========================
if __name__ == "__main__":
    ns = [4,5,6,7,8,9,10,11,12,13,14,15]
    for n in ns:
        coords = load_coordinates(n=n)

        dist = distance_matrix(coords)


        solver = CVRP_BnB(dist, capacity=5)
        start_time = time.time()
        solver.branch_and_bound()
        end_time = time.time() - start_time
        print("BnB Computing for:", n)
        print("Best routes:", solver.best_routes)
        print("Best cost:", solver.best_cost)
        print("Time of computing:", end_time)

