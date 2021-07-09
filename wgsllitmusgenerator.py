import os
import litmusgenerator

class WgslLitmusTest(litmusgenerator.LitmusTest):

    wgsl_stress_mem_location = "scratchpad.value[scratch_locations.value[workgroup_id]]"
    # returns the first access in the stress pattern
    wgsl_stress_first_access = {
        "store": ["{} = i;".format(wgsl_stress_mem_location)],
        "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location),
            "if (tmp1 > 100u) {", "  break;",
            "}"]
    }
    # given a first access, returns the second access in the stress pattern
    wgsl_stress_second_access = {
        "store": {
            "store": ["{} = i + 1u;".format(wgsl_stress_mem_location)],
            "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp1 > 100u) {", "  break;",
                "}"]
        },
        "load": {
            "store": ["{} = i;".format(wgsl_stress_mem_location)],
            "load": ["let tmp2: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp2 > 100u) {", "  break;",
                "}"]
        }
    }

    def file_ext(self):
        return ".wgsl"

    def generate_mem_loc(self, variable, mem_loc):
        return "  var {} : u32 = mem_locations.value[{}];".format(variable, mem_loc)

    def generate_thread_header(self):
        return [
            "if (stress_params.value[4] == 1u) {",
            "  do_stress(stress_params.value[5], stress_params.value[6], workgroup_id[0]);",
            "}",
            "if (stress_params.value[0] == 1u) {",
            "  spin();",
            "}"
        ]

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
            "[[group(0), binding(7)]] var<storage, read_write> stress_params : Memory;"
        ]
        return "\n".join(bindings)

    def generate_meta(self):
        return "\n\n".join([self.generate_types(), self.generate_bindings()])

    def generate_stress(self):
        body = ["fn do_stress(iterations: u32, pattern: u32, workgroup_id: u32) {", "for(var i: u32 = 0u; i < iterations; i = i + 1u) {"]
        i = 0
        for first in self.wgsl_stress_first_access:
            for second in self.wgsl_stress_second_access[first]:
                if i == 0:
                    body += ["  if (pattern == 0u) {"]
                else:
                    body += ["  }} elseif (pattern == {}u) {{".format(i)]
                body += ["    {}".format(statement) for statement in self.wgsl_stress_first_access[first]]
                body += ["    {}".format(statement) for statement in self.wgsl_stress_second_access[first][second]]
                i += 1
        body += ["  }", "}"]
        return "\n".join(["\n  ".join(body), "}"])

    def generate_spin(self):
        body = [
            "fn spin() {",
            "  var i : u32 = 0u;",
            "  var bar_val : u32 = atomicAdd(&barrier.value[0], 1u);",
            "  loop {",
            "    if (i == 1024u || bar_val >= {}u) {{".format(len(self.threads)),
            "      break;",
            "    }",
            "    bar_val = atomicLoad(&barrier.value[0]);",
            "    i = i + 1u;",
            "  }",
            "}"
        ]
        return "\n".join(body)

    def read_repr(self, instr):
        return "let {} = atomicLoad(&test_data.value[{}]);".format(instr.variable, instr.mem_loc)

    def write_repr(self, instr):
        return "atomicStore(&test_data.value[{}], {}u);".format(instr.mem_loc, instr.value)

    def fence_repr(self, instr):
        pass

    def results_repr(self, variable):
        return "atomicStore(&results.value[{}], {});".format(self.variables[variable], variable)

    def thread_filter(self, first_thread, workgroup, thread):
        if first_thread:
            start = "if"
        else:
            start = "} elseif"
        return start + " (shuffled_ids.value[global_invocation_id[0]] == workgroupXSize * {} + {}) {{".format(workgroup, thread)

    def generate_stress_call(self):
        return [
            "  } elseif (stress_params.value[1] == 1u) {",
            "    do_stress(stress_params.value[2], stress_params.value[3], workgroup_id[0]);",
            "  }"
        ]

    def generate_shader_def(self):
        return "\n".join([
            "let workgroupXSize = 1;",
            "[[stage(compute), workgroup_size(workgroupXSize)]] fn main([[builtin(workgroup_id)]] workgroup_id : vec3<u32>, [[builtin(global_invocation_id)]] global_invocation_id : vec3<u32>, [[builtin(local_invocation_index)]] local_invocation_index : u32) {"
        ])
