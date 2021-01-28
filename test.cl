__kernel void litmus_test(__global atomic_uint* test_memory) {
  atomic_store_explicit(&test_memory[0], get_num_groups(1), memory_order_relaxed);
}
