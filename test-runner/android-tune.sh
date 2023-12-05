#!/system/bin/sh

PARAM_FILE="params.txt"
RESULT_DIR="results"

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
  local stressLineSize=$(echo "$(random_between 2 10)^2" | bc)
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
  local test=$1
  local test_mem=$2
  local test_scope=$3
  res=$(./runner -n $test -s $test-$test_mem-$test_scope.spv -r $test-results.spv -p $PARAM_FILE -t $test-$test_mem-params.txt -d $device_idx)
  local device_used=$(echo "$res" | head -n 1 | sed 's/.*Using device \(.*\)$/\1/')
  local num_violations=$(echo "$res" | tail -n 1 | sed 's/.*of violations: \(.*\)$/\1/')
  echo "  Test $test-$test_mem-$test_scope violations: $num_violations"

  if [ $num_violations -gt 0 ] ; then
    if [ ! -d "$RESULT_DIR/$device_used" ] ; then
      mkdir "$RESULT_DIR/$device_used"
    fi
    if [ ! -d "$RESULT_DIR/$device_used/$iter-$test_mem" ] ; then
      mkdir "$RESULT_DIR/$device_used/$iter-$test_mem"
      cp $PARAM_FILE "$RESULT_DIR/$device_used/$iter-$test_mem"
    fi
    echo "Test: $test-$test_mem-$test_scope violations: $num_violations" >> "$RESULT_DIR/$device_used/$iter-$test_mem/violations.txt"
  fi

}

if [ $# != 1 ] ; then
  echo "Need to pass device index as first argument"
  exit 1
fi

device_idx=$1

if [ ! -d "$RESULT_DIR" ] ; then
  mkdir $RESULT_DIR
fi

test_names=("rr" "rw" "wr")
iter=0

while [ true ]
do
  echo "Iteration: $iter"

  # device memory tests
  random_config 128 128
  for test in "${test_names[@]}"; do
    run_test "$test" "mem-device" "scope-device"
    run_test "$test" "mem-device" "scope-wg"
  done

  # workgroup memory tests
  random_config 16 128 
  for test in "${test_names[@]}"; do
    run_test "$test" "mem-wg" "scope-wg"
  done

  iter=$((iter + 1))
done
