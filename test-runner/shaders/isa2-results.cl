typedef struct TestResults {
  atomic_uint seq0;
  atomic_uint seq1;
  atomic_uint seq2;
  atomic_uint seq3;
  atomic_uint interleaved;
  atomic_uint weak;
  atomic_uint other;
} TestResults;

static uint permute_id(uint id, uint factor, uint mask) {
  return (id * factor) % mask;
}

static uint stripe_workgroup(uint workgroup_id, uint local_id, uint testing_workgroups) {
  return (workgroup_id + 1 + local_id % (testing_workgroups - 1)) % testing_workgroups;
}

__kernel void litmus_test (
  __global atomic_uint* test_locations,
  __global atomic_uint* read_results,
  __global TestResults* test_results,
  __global uint* stress_params) {
  uint id_0 = get_global_id(0);
  uint x_0 = id_0 * stress_params[10] * 3;
  uint mem_x_0 = atomic_load(&test_locations[x_0]);
  uint r0 = atomic_load(&read_results[id_0 * 3]);
  uint r1 = atomic_load(&read_results[id_0 * 3 + 1]);
  uint r2 = atomic_load(&read_results[id_0 * 3 + 2]);

  if (r0 == 1 && r1 == 1 && r2 == 1) {
    atomic_fetch_add(&test_results->seq0, 1);
  } else if (r0 == 0 && r1 == 0 && r2 == 0) {
    atomic_fetch_add(&test_results->seq1, 1);
  } else if (r0 == 0 && r1 == 0 && r2 == 1) {
    atomic_fetch_add(&test_results->seq2, 1);
  } else if (r0 == 1 && r1 == 0 && r2 == 0) {
    atomic_fetch_add(&test_results->seq3, 1);
  } else if (r0 == 1 && r1 == 0 && r2 == 1) {
    atomic_fetch_add(&test_results->interleaved, 1);
  } else if (r0 == 1 && r1 == 1 && r2 == 0) {
    atomic_fetch_add(&test_results->weak, 1);
  } else {
    atomic_fetch_add(&test_results->other, 1);
  }
}
    
