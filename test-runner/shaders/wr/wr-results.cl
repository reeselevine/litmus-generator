typedef struct TestResults {
  atomic_uint seq0;
  atomic_uint seq1;
  atomic_uint interleaved0;
  atomic_uint interleaved1;
  atomic_uint not_bound;
  atomic_uint other;
} TestResults;

__kernel void check_results (
  __global uint* non_atomic_test_locations,
  __global atomic_uint* read_results,
  __global TestResults* test_results,
  __global uint* stress_params) {
  uint id_0 = get_global_id(0);
  uint flag = atomic_load(&read_results[id_0 * 2]); // flag
  uint r0 = atomic_load(&read_results[id_0 * 2 + 1]); // first read
  uint mem_val = non_atomic_test_locations[id_0 * stress_params[10]];
  if (flag == 1 && r0 == 3 && mem_val == 3) {
    atomic_fetch_add(&test_results->seq0, 1);
  } else if (flag == 0 && r0 == 3 && mem_val == 1) {
     atomic_fetch_add(&test_results->seq1, 1);
  } else if (flag == 0 && r0 == 1 && mem_val == 1) {
     atomic_fetch_add(&test_results->interleaved0, 1);
  } else if (flag == 0 && r0 == 3 && mem_val == 3) {
      atomic_fetch_add(&test_results->interleaved1, 1);
  } else if (flag == 1 && r0 == 1 && mem_val == 1) {
      atomic_fetch_add(&test_results->not_bound, 1);
  } else {
      atomic_fetch_add(&test_results->other, 1);
  }
}
