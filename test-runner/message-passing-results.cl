__kernel void litmus_test(
  __global atomic_uint* test_locations,
  __global atomic_uint* read_results,
  __global atomic_uint* test_results,
  __global uint* stress_params) {
  uint id_0 = get_global_id(0);
  uint r0 = atomic_load(&read_results[id_0 * 2]);
  uint r1 = atomic_load(&read_results[id_0 * 2 + 1]);
  if (r0 == 0 && r1 == 0) {
    atomic_fetch_add(&test_results[0], 1);
  } else if (r0 == 1 && r1 == 1) {
    atomic_fetch_add(&test_results[1], 1);
  } else if (r0 == 0 && r1 == 1) {
    atomic_fetch_add(&test_results[2], 1);
  } else if (r0 == 1 && r1 == 0) {
    atomic_fetch_add(&test_results[3], 1);
  }
}
