__kernel void litmus_test(__global atomic_uint* test_memory) {
  atomic_store_explicit(&test_memory[get_global_id(0)], 1, memory_order_relaxed);
}
