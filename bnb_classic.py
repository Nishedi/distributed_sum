import math
import random
import time

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

def lower_bound(dist, visited):
    lb = 0
    n = len(dist)
    for i in range(1, n):
        if not visited[i]:
            min_dist = min(dist[i][j] for j in range(n) if i != j)
            lb += min_dist
    return lb

class CVRP_BnB:
    def __init__(self, dist_matrix, capacity):
        self.dist = dist_matrix
        self.n = len(dist_matrix)
        self.C = capacity
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

        if all(visited):
            total_cost = current_cost + self.dist[route[-1]][0]
            all_routes = routes + [route + [0]]
            if total_cost < self.best_cost:
                self.best_cost = total_cost
                self.best_routes = all_routes
            return

        lb = current_cost + lower_bound(self.dist, visited)
        self.checks += 1
        if lb >= self.best_cost and cutting:
            self.cut+=1
            return

        for i in range(1, self.n):
            if not visited[i]:
                if current_load + 1 <= self.C:
                    visited[i] = True
                    self.branch_and_bound(route + [i], visited, current_load + 1,
                                          current_cost + self.dist[route[-1]][i], routes, cutting)
                    visited[i] = False

        if current_load > 0:
            self.branch_and_bound([0], visited, 0, current_cost, routes + [route], cutting)

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

