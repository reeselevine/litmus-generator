typedef struct TestResults {
  atomic_uint seq0;
  atomic_uint seq1;
  atomic_uint interleaved0;
  atomic_uint interleaved1;
  atomic_uint racy0;
  atomic_uint racy1;
  atomic_uint not_bound0;
  atomic_uint not_bound1;
  atomic_uint other;
} TestResults;

__kernel void check_results (
  __global atomic_uint* read_results,
  __global TestResults* test_results,
  __global uint* stress_params) {
  uint id_0 = get_global_id(0);
  uint flag = atomic_load(&read_results[id_0 * 3]); // flag
  uint r0 = atomic_load(&read_results[id_0 * 3 + 1]); // first read
  uint r1 = atomic_load(&read_results[id_0 * 3 + 2]); // second read
  if (flag == 1 && r0 == 2 && r1 == 2) {
    atomic_fetch_add(&test_results->seq0, 1);
  } else if (flag == 0 && r0 == 2 && r1 == 2) {
     atomic_fetch_add(&test_results->seq1, 1);
  } else if (flag == 1 && r0 == 1 && r1 == 1) {
     atomic_fetch_add(&test_results->interleaved0, 1);
  } else if (flag == 0 && r0 == 1 && r1 == 1) {
      atomic_fetch_add(&test_results->interleaved1, 1);
  } else if (flag == 0 && r0 == 2 && r1 == 1) {
      atomic_fetch_add(&test_results->racy0, 1);
  } else if (flag == 0 && r0 == 1 && r1 == 2) {
      atomic_fetch_add(&test_results->racy1, 1);
  } else if (flag == 1 && r0 == 2 && r1 == 1) {
      atomic_fetch_add(&test_results->not_bound0, 1);
  } else if (flag == 1 && r0 == 1 && r1 == 2) {
      atomic_fetch_add(&test_results->not_bound1, 1);
  } else {
    atomic_fetch_add(&test_results->other, 1);
  }
}
