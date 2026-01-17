cd distributed_sum
source ~/distributed_sum/venv/bin/activate
ray stop
ray start --address='156.17.41.136:6379'
exit
