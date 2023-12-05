#!/bin/bash

PARAM_FILE="params.txt"

# Generate a random number between min and max
function random_between() {
  local min=$1
  local max=$2

  local range=$((max - min + 1))
  local random=$((RANDOM % range + min))
  echo "$random"
}

function random_config() {
  local workgroupLimiter=$1
  local workgroupSizeLimiter=$2

  echo "testIterations=200" > $PARAM_FILE
  local testingWorkgroups=$(random_between 2 $workgroupLimiter)
  echo "testingWorkgroups=$testingWorkgroups" >> $PARAM_FILE
  local maxWorkgroups=$(random_between $testingWorkgroups $workgroupLimiter)
  echo "maxWorkgroups=$maxWorkgroups" >> $PARAM_FILE
  local workgroupSize=$(random_between 1 $workgroupSizeLimiter)
  echo "workgroupSize=$workgroupSize" >> $PARAM_FILE
  echo "shufflePct=$(random_between 0 100)" >> $PARAM_FILE
  echo "barrierPct=$(random_between 0 100)" >> $PARAM_FILE
  local stressLineSize=$(($(random_between 2 10) ** 2))
  echo "stressLineSize=$stressLineSize" >> $PARAM_FILE
  local stressTargetLines=$(random_between 1 16)
  echo "stressTargetLines=$stressTargetLines" >> $PARAM_FILE
  echo "scratchMemorySize=$((32 * $stressLineSize * $stressTargetLines))" >> $PARAM_FILE
  echo "memStride=$(random_between 1 7)" >> $PARAM_FILE
  echo "memStressPct=$(random_between 0 100)" >> $PARAM_FILE
  echo "memStressIterations=$(random_between 0 1024)" >> $PARAM_FILE
  echo "memStressPattern=$(random_between 0 3)" >> $PARAM_FILE
  echo "preStressPct=$(random_between 0 100)" >> $PARAM_FILE
  echo "preStressIterations=$(random_between 0 128)" >> $PARAM_FILE
  echo "preStressPattern=$(random_between 0 3)" >> $PARAM_FILE
  echo "stressAssignmentStrategy=$(random_between 0 1)" >> $PARAM_FILE
  echo "permuteThread=419" >> $PARAM_FILE
}

function run_test() {
  local test_name=$1
  local test_shader=$2
  local test_result_shader=$3
  local test_params=$4
  res=$(./runner -n $test_name -s $test_shader -r $test_result_shader -p $PARAM_FILE -t $test_params -d $device_idx)
  local device_used=$(echo "$res" | head -n 1 | sed 's/.*Using device \(.*\)$/\1/')
  local weak_behaviors=$(echo "$res" | tail -n 1 | sed 's/.*of weak behaviors: \(.*\)$/\1/')
  echo "  Device $device_used Test $test_shader weak behaviors: $weak_behaviors"
}

if [ $# != 1 ] ; then
  echo "Need to pass device index as first argument"
  exit 1
fi

device_idx=$1

readarray tests < shaders.txt

iter=0

while [ true ]
do
  echo "Iteration: $iter"
  random_config 1024 256
  for test in "${tests[@]}"; do
    test_info=(${test})
    echo $test_info
    run_test "${test_info[0]}" "${test_info[1]}" "${test_info[2]}" "${test_info[3]}"
  done
  iter=$((iter + 1))
done
