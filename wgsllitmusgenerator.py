import os
import litmusgenerator

class WgslLitmusGenerator(litmusgenerator.LitmusTest):

    wgsl_stress_mem_location = "scratchpad.value[scratch_locations.value[get_group_id(0)]]"
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

    def generate_types(self):
        atomic_arr_type = ["[[block]] struct AtomicMemory {", "  value: array<atomic<u32>>;", "};"]
        normal_type = ["[[block]] struct Memory {", "  value: array<u32>;", "};"]
        return "\n".join(atomic_type + normal_type)

    def generate_bindings(self):
        bindings = [
            "[[group(0), binding(0)]] var<storage, read_write> test_data : AtomicMemory",
            "[[group(0), binding(1)]] var<storage, read_write> mem_locations : Memory",
            "[[group(0), binding(2)]] var<storage, read_write> results : AtomicMemory",
            "[[group(0), binding(3)]] var<storage, read_write> shuffled_ids : Memory",
            "[[group(0), binding(4)]] var<storage, read_write> barrier : AtomicMemory",
            "[[group(0), binding(5)]] var<storage, read_write> scratchpad : Memory",
            "[[group(0), binding(6)]] var<storage, read_write> scratch_locations : Memory",
            "[[group(0), binding(6)]] var<storage, read_write> stress_params : Memory"
        ]
        return "\n".join(bindings)
    
    def generate_stress(self):
        body = ["[[stage(compute)]] fn do_stress(iterations: u32, pattern: u32) {", "for(var i: u32 = 0, i < iterations, i = i + 1) {"]
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
            "  let val = atomicAdd(&barrier.value[0], 1);",
            "  loop {",
            "    if (i == 1024 || val >= {}) {{".format(len(self.threads)),
            "      break;",
            "    }",
            "    val = atomicLoad(&barrier.value[0]);",
            "    i = i + 1;",
            "  }",
            "}"
        ]
        return "\n".join(body)