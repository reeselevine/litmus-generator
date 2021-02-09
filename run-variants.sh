#!/bin/bash
#litmusTests=("message-passing" "load-buffer" "store-buffer" "isa2" "iriw" "store" "read", "2+2-write")
litmusTests=("store" "read", "2+2-write")

for i in "${litmusTests[@]}"
do
    python3 litmustestrunner.py $i --configdir litmus-config/$i-variants/ -grv --outputfile $i-variants.csv
done
