import os
import litmusgenerator

class WgslLitmusTest(litmusgenerator.LitmusTest):

    wgsl_stress_mem_location = "scratchpad.value[scratch_locations.value[workgroup_id[0]]]"
    # returns the first access in the stress pattern
    wgsl_stress_first_access = {
        "store": ["{} = i;".format(wgsl_stress_mem_location)],
        "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location), 
            "if (tmp1 > 100) {", "  break;",
            "}"]
    }
    # given a first access, returns the second access in the stress pattern
    wgsl_stress_second_access = {
        "store": {
            "store": ["{} = i + 1;".format(wgsl_stress_mem_location)],
            "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp1 > 100) {", "  break;",
                "}"]
        },
        "load": {
            "store": ["{} = i;".format(wgsl_stress_mem_location)],
            "load": ["let tmp2: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp2 > 100) {", "  break;",
                "}"]
        }
    }

    def generate(self):
        body_statements = []
        first_thread = True
        variable_init = []
        for variable, mem_loc in self.memory_locations.items():
            body_statements.append("  var {} : u32 = mem_locations.value[{}];".format(variable, mem_loc))
        for thread in self.threads:
            variables = set()
            thread_statements = ["if (stress_params.value[4]) {", "  do_stress(stress_params.value[5], stress_params.value[6]);", "}"]
            thread_statements = thread_statements + ["if (stress_params.value[0]) {", "  spin();", "}"]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements.append(self.wgsl_repr(instr))
            for variable in variables:
                thread_statements.append("atomicStore(&results.value[{}], {});".format(self.variables[variable], variable))
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(first_thread))] + thread_statements
            first_thread = False
        body_statements = body_statements + ["  \n".join(["  } elseif (stress_params.value[1]) {", "    do_stress(stress_params.value[2], stress_params.value[3]);", "  }"])]
        shader_def = "[[stage(compute)]] fn main([[builtin(workgroup_id) workgroup_id : vec3<u32>, [[builtin(global_invocation_id)]] global_invocation_id : vec3<u32>, [[builtin(local_invocation_index)]] local_invocation_index : u32) {"
        shader = "\n".join([shader_def] + body_statements + ["}\n"])
        shader_types = self.generate_types()
        bindings = self.generate_bindings()
        spin_func = self.generate_spin()
        stress_func = self.generate_stress()
        shader = "\n\n".join([shader_types, bindings, spin_func, stress_func, shader])
        filename = "target/" + self.test_name + ".wgsl"
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as output_file:
            output_file.write(shader)


    def generate_types(self):
        atomic_type = ["[[block]] struct AtomicMemory {", "  value: array<atomic<u32>>;", "};"]
        normal_type = ["[[block]] struct Memory {", "  value: array<u32>;", "};"]
        return "\n".join(atomic_type + normal_type)

    def generate_bindings(self):
        bindings = [
            "[[group(0), binding(0)]] var<storage, read_write> test_data : AtomicMemory;",
            "[[group(0), binding(1)]] var<storage, read_write> mem_locations : Memory;",
            "[[group(0), binding(2)]] var<storage, read_write> results : AtomicMemory;",
            "[[group(0), binding(3)]] var<storage, read_write> shuffled_ids : Memory;",
            "[[group(0), binding(4)]] var<storage, read_write> barrier : AtomicMemory;",
            "[[group(0), binding(5)]] var<storage, read_write> scratchpad : Memory;",
            "[[group(0), binding(6)]] var<storage, read_write> scratch_locations : Memory;",
            "[[group(0), binding(6)]] var<storage, read_write> stress_params : Memory;"
        ]
        return "\n".join(bindings)
    
    def generate_stress(self):
        body = ["[[stage(compute)]] fn do_stress(iterations: u32, pattern: u32) {", "for(var i: u32 = 0; i < iterations; i = i + 1) {"]
        i = 0
        for first in self.wgsl_stress_first_access:
            for second in self.wgsl_stress_second_access[first]:
                if i == 0:
                    body += ["  if (pattern == 0) {"]
                else:
                    body += ["  }} elseif (pattern == {}) {{".format(i)]
                body += ["    {}".format(statement) for statement in self.wgsl_stress_first_access[first]]
                body += ["    {}".format(statement) for statement in self.wgsl_stress_second_access[first][second]]
                i += 1
        body += ["  }", "}"]
        return "\n".join(["\n  ".join(body), "}"])

    def generate_spin(self):
        body = [
            "[[stage(compute)]] fn spin() {",
            "  var i : u32 = 0;",
            "  var bar_val : u32 = atomicAdd(&barrier.value[0], 1);",
            "  loop {",
            "    if (i == 1024 || bar_val >= {}) {{".format(len(self.threads)),
            "      break;",
            "    }",
            "    bar_val = atomicLoad(&barrier.value[0]);",
            "    i = i + 1;",
            "  }",
            "}"
        ]
        return "\n".join(body)
    
    def wgsl_repr(self, instr):
        if isinstance(instr, self.ReadInstruction):
            return "let {} = atomicLoad(&test_data.value[{}]);".format(instr.variable, instr.mem_loc)
        elif isinstance(instr, self.WriteInstruction):
            return "atomicStore(&test_data.value[{}], {});".format(instr.mem_loc, instr.value)
        elif isinstance(instr, self.MemoryFence):
            pass

    def thread_filter(self, first_thread):
        if first_thread:
            start = "if"
        else:
            start = "} elseif"
        return start + " (shuffled_ids.value[global_invocation_id[0]] == local_invocation_index) {"

