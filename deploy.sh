#!/bin/bash

NODES=$(cat nodes.txt)
SRC_DIR=$(pwd)

for node in $NODES; do
    echo "Deploying to $node..."
    scp -r cpp python nodes.txt cluster@$node:/home/cluster/distributed_sum
    ssh cluster@$node "
        cd ~/distributed_sum &&
        # jeśli venv nie istnieje, tworzymy
        python3 -m venv venv &&
        source venv/bin/activate &&
        pip install --upgrade pip &&
        pip install ray numpy &&
        g++ -O3 -fPIC -shared cpp/distributed_bnb.cpp -o cpp/libcvrp.so &&
        g++ -O3 -fPIC -shared cpp/sum_array.cpp -o cpp/libsum.so
    "
done
