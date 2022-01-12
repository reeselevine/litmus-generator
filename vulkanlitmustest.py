import litmustest

class VulkanLitmusTest(litmustest.LitmusTest):

    opencl_stress_mem_location = "scratchpad[scratch_locations[get_group_id(0)]]"
    # returns the first access in the stress pattern
    openCL_stress_first_access = {
        "store": ["{} = i;".format(opencl_stress_mem_location)],
        "load": ["uint tmp1 = {};".format(opencl_stress_mem_location),
            "if (tmp1 > 100) {", "  break;",
            "}"]
    }
    # given a first access, returns the second access in the stress pattern
    openCL_stress_second_access = {
        "store": {
            "store": ["{} = i + 1;".format(opencl_stress_mem_location)],
            "load": ["uint tmp1 = {};".format(opencl_stress_mem_location),
                "if (tmp1 > 100) {", "  break;",
                "}"]
        },
        "load": {
            "store": ["{} = i;".format(opencl_stress_mem_location)],
            "load": ["uint tmp2 = {};".format(opencl_stress_mem_location),
                "if (tmp2 > 100) {", "  break;",
                "}"]
        }
    }

    openCL_mem_order = {
            "relaxed": "memory_order_relaxed",
            "sc": "memory_order_seq_cst",
            "acquire": "memory_order_acquire",
            "release": "memory_order_release",
            "acq_rel": "memory_order_acq_rel"
        }

    # Code below this line generates the actual opencl kernel

    def file_ext(self):
        return ".cl"

    def generate_mem_loc(self, variable, mem_loc):
        return "  const uint {} = mem_locations[{}];".format(variable, mem_loc)

    def generate_thread_header(self):
        return [
            "if (stress_params[4]) {",
            "  do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);",
            "}",
            "if (stress_params[0]) {",
            "  spin(barrier);",
            "}"
        ]

    def read_repr(self, instr):
        return "uint {} = atomic_load_explicit(&test_data[{}], {});".format(instr.variable, instr.mem_loc, self.openCL_mem_order[instr.mem_order])

    def write_repr(self, instr):
        return "atomic_store_explicit(&test_data[{}], {}, {});".format(instr.mem_loc, instr.value, self.openCL_mem_order[instr.mem_order])

    def fence_repr(self, instr):
        return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, {}, memory_scope_device);".format(self.openCL_mem_order[instr.mem_order])

    def results_repr(self, variable):
        return "atomic_store_explicit(&results[{}], {}, {});".format(self.variables[variable], variable, "memory_order_seq_cst")

    def generate_meta(self):
        return ""

    def generate_stress(self):
        body = ["static void do_stress(__global uint* scratchpad, __global uint* scratch_locations, uint iterations, uint pattern) {",
                "for (uint i = 0; i < iterations; i++) {"]
        i = 0
        for first in self.openCL_stress_first_access:
            for second in self.openCL_stress_second_access[first]:
                if i == 0:
                    body += ["  if (pattern == 0) {"]
                else:
                    body += ["  }} else if (pattern == {}) {{".format(i)]
                body += ["    {}".format(statement) for statement in self.openCL_stress_first_access[first]]
                body += ["    {}".format(statement) for statement in self.openCL_stress_second_access[first][second]]
                i += 1
        body += ["  }", "}"]
        return "\n".join(["\n  ".join(body), "}"])

    def generate_spin(self):
        header = "static void spin(__global atomic_uint* barrier) {"
        body = "\n  ".join([
            header,
            "int i = 0;",
            "uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
            "while (i < 1024 && val < {}) {{".format(len(self.threads)),
            "  val = atomic_load_explicit(barrier, memory_order_relaxed);",
            "  i++;",
            "}"
        ])
        return "\n".join([body, "}"])

    def thread_filter(self, first_thread, workgroup, thread):
        if first_thread:
            start = "if"
        else:
            start = "} else if"
        return start + " (shuffled_ids[get_global_id(0)] == get_local_size(0) * {} + {}) {{".format(workgroup, thread)

    def generate_stress_call(self):
        return [
            "  } else if (stress_params[1]) {",
            "    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);",
            "  }"
        ]

    def generate_shader_def(self):
        kernel_args = ["__global atomic_uint* test_data", "__global uint* mem_locations", "__global atomic_uint* results", "__global uint* shuffled_ids","__global atomic_uint* barrier", "__global uint* scratchpad", "__global uint* scratch_locations", "__global uint* stress_params"]
        return "__kernel void litmus_test(\n  " + ",\n  ".join(kernel_args) + ") {"
