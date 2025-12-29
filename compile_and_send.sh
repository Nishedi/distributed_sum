g++ -O3 -fPIC -shared cpp/sum_array.cpp -o cpp/libsum.so
scp cpp/libsum.so cluster@cluster600:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster601:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster602:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster603:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster604:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster605:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster606:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster607:/home/cluster/distributed_sum/cpp
scp cpp/libsum.so cluster@cluster608:/home/cluster/distributed_sum/cpp
