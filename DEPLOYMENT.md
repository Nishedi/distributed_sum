# Deployment Instructions for Performance Improvements

## Step 1: Recompile the C++ Library

The C++ code has been updated to include the new `solve_from_two_cities` function.
You need to recompile the library on your cluster:

```bash
cd cpp
g++ -shared -fPIC -O2 distributed_bnb.cpp -o libcvrp.so
```

Verify the compilation:
```bash
ls -lh libcvrp.so
file libcvrp.so
```

## Step 2: Deploy the Library to All Nodes

The updated `libcvrp.so` needs to be present on all cluster nodes in the expected location:
- `/home/cluster/distributed_sum/cpp/libcvrp.so`

You can use your existing deployment script:
```bash
./compile_and_send.sh
# or
./compile_and_send2.sh
```

Or manually copy to all nodes listed in `nodes.txt`:
```bash
for node in $(cat nodes.txt); do
    scp cpp/libcvrp.so $node:/home/cluster/distributed_sum/cpp/
done
```

## Step 3: Update Python Files

The Python files have already been updated:
- `python/ray_cvrp.py` - Added BoundTracker and solve_city_pair
- `python/run_ray.py` - Added comparative tests

Deploy these to your cluster:
```bash
for node in $(cat nodes.txt); do
    scp python/ray_cvrp.py $node:/home/cluster/distributed_sum/python/
    scp python/run_ray.py $node:/home/cluster/distributed_sum/python/
done
```

## Step 4: Run Tests

### Local Test (No Ray Required)
```bash
python test_improvements.py
```

### Distributed Test (On Cluster)
```bash
# On the head node
python python/run_ray.py
```

This will run 5 different test scenarios:
1. BnB without shared bound (original)
2. BnB_SP without shared bound (original)
3. BnB with shared bound (improved)
4. BnB_SP with shared bound (improved)
5. BnB with fine-grained tasks (most improved)

## Expected Results

You should see significant improvements:

### Before
- Speedup with 9 nodes: ~1.7-1.8x

### After (with shared bound)
- Speedup with 9 nodes: ~2-3x

### After (with fine-grained tasks)
- Speedup with 9 nodes: ~3-5x

## Troubleshooting

### Library Not Found
If you get an error about libcvrp.so not found:
1. Check the path in `python/ray_cvrp.py` line 10-11
2. Update `LIB_PATH` to match your cluster configuration
3. Ensure the library is present on all worker nodes

### Ray Connection Issues
If Ray workers can't connect:
```bash
ray status  # Check cluster status
ray start --head  # Start head node if needed
```

### Symbol Not Found Errors
If you get errors about missing functions:
1. Make sure you recompiled the C++ library with the updated code
2. Check that the new library has been deployed to all nodes
3. Verify: `nm -D cpp/libcvrp.so | grep solve_from_two_cities`

## Rollback

If you need to revert to the original version:
```bash
git checkout HEAD~1 python/ray_cvrp.py python/run_ray.py cpp/distributed_bnb.cpp
cd cpp
g++ -shared -fPIC -O2 distributed_bnb.cpp -o libcvrp.so
```

## Questions?

See the detailed documentation:
- Polish: `PERFORMANCE_IMPROVEMENTS.md`
- English: `PERFORMANCE_IMPROVEMENTS_EN.md`
