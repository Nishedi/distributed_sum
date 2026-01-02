# Distributed CVRP Solver

Rozproszone rozwiązanie problemu CVRP (Capacitated Vehicle Routing Problem) z wykorzystaniem algorytmu Branch and Bound.

**Distributed CVRP Solver** using Branch and Bound algorithm with multiple implementation approaches.

## 🚀 Quick Start

```bash
# For local multi-core parallelism (recommended for development)
python python/run_multiprocessing.py --n 14 --C 5

# For Ray cluster (requires cluster setup)
python python/run_ray.py --n 14 --C 5

# For sequential baseline
python bnb_classic.py
```

## 📊 Three Approaches

This repository implements three different approaches to solving CVRP:

### 1. 🔄 Multiprocessing (NEW!)
**Best for: Development, prototyping, single machines**

```bash
python python/run_multiprocessing.py --n 14 --C 5
```

- ✅ Zero configuration
- ✅ 4-9x speedup on multi-core machines
- ✅ Shared bound tracking
- ✅ Perfect for laptops/workstations
- 📖 [Polish Documentation](MULTIPROCESSING.md) | [English Documentation](MULTIPROCESSING_EN.md)

### 2. 🌐 Ray Distributed
**Best for: Production, multi-node clusters**

```bash
python python/run_ray.py --n 14 --C 5
```

- ✅ Scales to multiple nodes
- ✅ 3-5x speedup on 9-node cluster
- ✅ Advanced features (fault tolerance, monitoring)
- ✅ Best for large problems
- 📖 [Performance Improvements (Polish)](PERFORMANCE_IMPROVEMENTS.md) | [English](PERFORMANCE_IMPROVEMENTS_EN.md)

### 3. 📝 Classic Sequential
**Best for: Baseline comparison, small problems**

```bash
python bnb_classic.py
```

- ✅ Simple, easy to understand
- ✅ No dependencies
- ✅ Good for n ≤ 10

## 📈 Performance Comparison

| Approach | Setup | n=12, 4 cores | n=14, 9 nodes | Best Use Case |
|----------|-------|---------------|---------------|---------------|
| Classic BnB | None | 1.17s (1x) | - | Small problems |
| **Multiprocessing** | **None** | **0.14s (8.5x)** | - | **Development** |
| Ray Cluster | Cluster | - | ~18s (4-5x) | **Production** |

## 🛠️ Setup

### Prerequisites
```bash
# Install dependencies
pip install numpy

# Compile C++ library
cd cpp
g++ -shared -fPIC -O2 distributed_bnb.cpp -o libcvrp.so
cd ..
```

### For Ray Cluster (optional)
```bash
pip install ray
# Setup Ray cluster - see DEPLOYMENT.md
```

## 🧪 Testing

```bash
# Test multiprocessing implementation
python test_multiprocessing.py

# Compare all approaches
python compare_approaches.py 10 5

# Full test suite
python test_improvements.py
```

## 📚 Documentation

### Core Documentation
- **[MULTIPROCESSING.md](MULTIPROCESSING.md)** - Multiprocessing approach (Polish)
- **[MULTIPROCESSING_EN.md](MULTIPROCESSING_EN.md)** - Multiprocessing approach (English)
- **[SUMMARY.md](SUMMARY.md)** - Complete overview of all changes
- **[QUICKSTART.md](QUICKSTART.md)** - Quick start guide

### Ray Cluster Documentation
- **[PERFORMANCE_IMPROVEMENTS.md](PERFORMANCE_IMPROVEMENTS.md)** - Ray improvements (Polish)
- **[PERFORMANCE_IMPROVEMENTS_EN.md](PERFORMANCE_IMPROVEMENTS_EN.md)** - Ray improvements (English)
- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Cluster deployment guide

## 🎯 Which Approach Should I Use?

### Use Multiprocessing if:
- 🖥️ Working on a single multi-core machine
- 🔬 Prototyping or developing
- ⚡ Want quick setup without cluster configuration
- 📊 Solving problems with n ≤ 15
- 🎓 Learning or teaching distributed algorithms

### Use Ray if:
- 🌐 Have access to a cluster (multiple nodes)
- 📈 Need to scale beyond single machine
- 🏭 Running in production
- 🔧 Can maintain Ray infrastructure
- 📊 Solving large problems with n > 15

### Use Classic if:
- 📝 Want to understand the algorithm
- 🧪 Need a baseline for comparison
- 🎯 Solving very small problems (n ≤ 10)

## 🏗️ Repository Structure

```
distributed_sum/
├── cpp/
│   ├── distributed_bnb.cpp      # C++ Branch and Bound implementation
│   └── libcvrp.so               # Compiled library
├── python/
│   ├── multiprocessing_cvrp.py  # NEW: Multiprocessing implementation
│   ├── run_multiprocessing.py   # NEW: Multiprocessing benchmark
│   ├── ray_cvrp.py              # Ray distributed implementation
│   ├── run_ray.py               # Ray benchmark
│   └── greedy.py                # Greedy heuristic
├── bnb_classic.py               # Classic sequential BnB
├── test_multiprocessing.py      # NEW: Multiprocessing tests
├── compare_approaches.py        # NEW: Comparison tool
├── test_improvements.py         # Test suite
├── MULTIPROCESSING.md           # NEW: Multiprocessing docs (PL)
├── MULTIPROCESSING_EN.md        # NEW: Multiprocessing docs (EN)
├── SUMMARY.md                   # Complete summary
└── README.md                    # This file
```

## 📊 Example Results

### Multiprocessing on 4-core machine (n=12, C=5)
```
Greedy solution: 59511.27
1 worker:  1.17s → 30377.00
4 workers: 0.14s → 30681.00
Speedup: 8.5x ⚡
```

### Ray on 9-node cluster (n=14, C=5)
```
Original (9 nodes): 48.26s
Improved (9 nodes): ~18s
Speedup: 2.7x → 4.8x ⚡
```

## 🤝 Contributing

Contributions are welcome! Please ensure:
- Code passes all tests
- Documentation is updated
- Follows existing code style

## 📄 License

[Add your license here]

## 👥 Authors

- Original implementation: [Author names]
- Multiprocessing approach: Added via GitHub Copilot (2026)
- Ray improvements: [Author names]

## 🔗 References

- CVRP Problem: [Wikipedia](https://en.wikipedia.org/wiki/Vehicle_routing_problem)
- Branch and Bound: [Wikipedia](https://en.wikipedia.org/wiki/Branch_and_bound)
- Ray Framework: [ray.io](https://www.ray.io/)
- Python Multiprocessing: [Python Docs](https://docs.python.org/3/library/multiprocessing.html)

---

**Star this repository if you find it useful! ⭐**
