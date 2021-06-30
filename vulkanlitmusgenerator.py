import os
import litmusgenerator

class VulkanLitmusTest(litmusgenerator.LitmusTest):

    openCL_stress_mem_location = "scratchpad[scratch_locations[get_group_id(0)]]"
    # Returns the first access in the stress pattern
    openCL_stress_first_access = {
        "store": ["{} = i;".format(openCL_stress_mem_location)],
        "load": ["uint tmp1 = {};".format(openCL_stress_mem_location), 
            "if (tmp1 > 100) {", "  break;",
            "}"]
    }
    # Given a first access, returns the second access in the stress pattern
    openCL_stress_second_access = {
        "store": {
            "store": ["{} = i + 1;".format(openCL_stress_mem_location)],
            "load": ["uint tmp1 = {};".format(openCL_stress_mem_location),
                "if (tmp1 > 100) {", "  break;",
                "}"]
        },
        "load": {
            "store": ["{} = i;".format(openCL_stress_mem_location)],
            "load": ["uint tmp2 = {};".format(openCL_stress_mem_location),
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

    def generate(self):
        self.generate_openCL_kernel()

    def generate_openCL_kernel(self):
        body_statements = []
        first_thread = True
        variable_initializations = []
        for variable, mem_loc in self.memory_locations.items():
           body_statements.append("  const uint {} = mem_locations[{}];".format(variable, mem_loc))
        for thread in self.threads:
            variables = set()
            thread_statements = ["if (stress_params[4]) {", "  do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);", "}"]
            thread_statements = thread_statements + ["if (stress_params[0]) {", "  spin(barrier);", "}"]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements.append(self.openCL_repr(instr))
            for variable in variables:
                thread_statements.append("atomic_store_explicit(&results[{}], {}, {});".format(self.variables[variable], variable, "memory_order_seq_cst"))
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(thread.workgroup, thread.local_id, first_thread))] + thread_statements
            first_thread = False
        body_statements = body_statements + ["  \n".join(["  } else if (stress_params[1]) {", "    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);", "  }"])]
        kernel_args = ["__global atomic_uint* test_data", "__global uint* mem_locations", "__global atomic_uint* results", "__global uint* shuffled_ids","__global atomic_uint* barrier", "__global uint* scratchpad", "__global uint* scratch_locations", "__global uint* stress_params"]
        kernel_func_def = "__kernel void litmus_test(\n  " + ",\n  ".join(kernel_args) + ") {"
        kernel = "\n".join([kernel_func_def] + body_statements + ["}\n"])
        spin_func = self.generate_spin()
        stress_func = self.generate_stress()
        kernel = "\n\n".join([spin_func, stress_func, kernel])
        filename = "target/" + self.test_name + ".cl"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as output_file:
            output_file.write(kernel)

    def openCL_repr(self, instr):
        if isinstance(instr, self.ReadInstruction):
            return "uint {} = atomic_load_explicit(&test_data[{}], {});".format(instr.variable, instr.mem_loc, self.openCL_mem_order[instr.mem_order])
        elif isinstance(instr, self.WriteInstruction):
            return "atomic_store_explicit(&test_data[{}], {}, {});".format(instr.mem_loc, instr.value, self.openCL_mem_order[instr.mem_order])
        elif isinstance(instr, self.MemoryFence):
            return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, {}, memory_scope_device);".format(self.openCL_mem_order[instr.mem_order])

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

    def thread_filter(self, workgroup, thread, first_thread):
        if first_thread:
            start = "if"
        else:
            start = "} else if"
        return start + " (shuffled_ids[get_global_id(0)] == get_local_size(0) * {} + {}) {{".format(workgroup, thread)
