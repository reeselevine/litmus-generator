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

static uint permute_id(uint id, uint factor, uint mask) {
  return (id * factor) % mask;
}

static uint stripe_workgroup(uint workgroup_id, uint local_id, uint testing_workgroups) {
  return (workgroup_id + 1 + local_id % (testing_workgroups - 1)) % testing_workgroups;
}

__kernel void litmus_test (
  __global atomic_uint* test_locations,
  __global atomic_uint* read_results,
  __global uint* shuffled_workgroups,
  __global atomic_uint* barrier,
  __global uint* scratchpad,
  __global uint* scratch_locations,
  __global uint* stress_params) {
  uint shuffled_workgroup = shuffled_workgroups[get_group_id(0)];
  if (shuffled_workgroup < stress_params[9]) {
    uint total_ids = get_local_size(0) * stress_params[9];
    uint id_0 = shuffled_workgroup * get_local_size(0) + get_local_id(0);
    uint new_workgroup = stripe_workgroup(shuffled_workgroup, get_local_id(0), stress_params[9]);
    uint id_1 = new_workgroup * get_local_size(0) + permute_id(get_local_id(0), stress_params[7], get_local_size(0));
    uint x_0 = id_0 * stress_params[10] * 2;
    uint y_0 = (permute_id(id_0, stress_params[8], total_ids)) * stress_params[10] * 2 + stress_params[11];
    uint y_1 = (permute_id(id_1, stress_params[8], total_ids)) * stress_params[10] * 2 + stress_params[11];
    uint x_1 = id_1 * stress_params[10] * 2;
    if (stress_params[4]) {
      do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);
    }
    if (stress_params[0]) {
      spin(barrier, get_local_size(0) * stress_params[9]);
    }
    atomic_store_explicit(&test_locations[x_0], 1, memory_order_relaxed);
    atomic_store_explicit(&test_locations[y_0], 1, memory_order_release);
    uint r0 = atomic_load_explicit(&test_locations[y_1], memory_order_acquire);
    uint r1 = atomic_load_explicit(&test_locations[x_1], memory_order_relaxed);
    atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);
    atomic_store(&read_results[id_1*2], r0);
    atomic_store(&read_results[id_1*2 + 1], r1);
  } else if (stress_params[1]) {
    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);
  }
}
