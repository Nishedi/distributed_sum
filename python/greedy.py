import numpy as np

def greedy_cvrp_1nn(dist, C=5):
    n = dist.shape[0]

    visited = [False] * n
    visited[0] = True

    route = [0]
    total_cost = 0.0

    current = 0
    load = 0

    while not all(visited):
        if load == C:
            total_cost += dist[current][0]
            route.append(0)
            current = 0
            load = 0
            continue

        nearest = None
        nearest_dist = float("inf")

        for i in range(1, n):
            if not visited[i] and dist[current][i] < nearest_dist:
                nearest = i
                nearest_dist = dist[current][i]

        if nearest is None:
            total_cost += dist[current][0]
            route.append(0)
            break

        total_cost += nearest_dist
        route.append(nearest)
        visited[nearest] = True
        current = nearest
        load += 1

    if route[-1] != 0:
        total_cost += dist[current][0]
        route.append(0)

    return route, total_cost