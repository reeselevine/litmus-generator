static uint permute_id(uint id, uint factor, uint mask) {
  return (id * factor) % mask;
}

static void spin(__global atomic_uint* barrier, uint limit) {
  int i = 0;
  uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);
  while (i < 1024 && val < limit) {
    val = atomic_load_explicit(barrier, memory_order_relaxed);
    i++;
  }
}

static void do_stress(__global uint* scratchpad, __global uint* scratch_locations, uint iterations, uint pattern) {
  for (uint i = 0; i < iterations; i++) {
    if (pattern == 0) {
      scratchpad[scratch_locations[get_group_id(0)]] = i;
      scratchpad[scratch_locations[get_group_id(0)]] = i + 1;
    } else if (pattern == 1) {
      scratchpad[scratch_locations[get_group_id(0)]] = i;
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
    } else if (pattern == 2) {
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
      scratchpad[scratch_locations[get_group_id(0)]] = i;
    } else if (pattern == 3) {
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
      uint tmp2 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp2 > 100) {
        break;
      }
    }
  }
}

__kernel void run_test (
  __local uint* wg_non_atomic_test_locations,
  __local atomic_uint* wg_atomic_test_locations,
  __global uint* read_results,
  __global uint* shuffled_workgroups,
  __global atomic_uint* _barrier,
  __global uint* scratchpad,
  __global uint* scratch_locations,
  __global uint* stress_params) {

  wg_non_atomic_test_locations[get_local_id(0) * stress_params[10]] = 0; // local memory is not zero initialized by default
  atomic_store_explicit(&wg_atomic_test_locations[get_local_id(0) * stress_params[10]], 0, memory_order_relaxed);

  barrier(CLK_LOCAL_MEM_FENCE); // ensure all threads in the workgroup see zero initialized memory

  uint shuffled_workgroup = shuffled_workgroups[get_group_id(0)];
  if(shuffled_workgroup < stress_params[9]) {
    uint total_ids = get_local_size(0);
    uint id_0 = get_local_id(0);
    uint id_1 = permute_id(get_local_id(0), stress_params[7], get_local_size(0));
    uint x_0 = (id_0) * stress_params[10]; // used to write to the racy location and write the flag (thread 0)
    uint x_1 = (id_1) * stress_params[10]; // used to write to the racy location, read the flag, first read of racy location (thread 1)
    uint y_1 = (permute_id(id_1, stress_params[8], total_ids)) * stress_params[10]; // aliased second read of racy location (thread 1)
    if (stress_params[4]) {
      do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);
    }
    if (stress_params[0]) {
      spin(_barrier, get_local_size(0));
    }
    // Thread 0
    wg_non_atomic_test_locations[x_0] = 1;
    atomic_store_explicit(&wg_atomic_test_locations[x_0], 1, memory_order_release);

    // Thread 1
    wg_non_atomic_test_locations[x_1] = 2;
    uint flag = atomic_load_explicit(&wg_atomic_test_locations[x_1], memory_order_acquire);
    uint r0 = wg_non_atomic_test_locations[x_1];
    uint r1 = wg_non_atomic_test_locations[y_1]; 

    // Store back results for analysis
    read_results[(shuffled_workgroup * get_local_size(0) + id_1) * 3] = flag;
    read_results[(shuffled_workgroup * get_local_size(0) + id_1) * 3 + 2] = r1;
    read_results[(shuffled_workgroup * get_local_size(0) + id_1) * 3 + 1] = r0;
  } else if (stress_params[1]) {
    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);
  }
}
