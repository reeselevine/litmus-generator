import os
import litmusgenerator

class WgslLitmusTest(litmusgenerator.LitmusTest):

    wgsl_stress_mem_location = "scratchpad.value[addr]"
    # returns the first access in the stress pattern
    wgsl_stress_first_access = {
        "store": ["{} = i;".format(wgsl_stress_mem_location)],
        "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location),
            "if (tmp1 > 100000u) {",
            "  {} = i;".format(wgsl_stress_mem_location),
            "  break;",
            "}"]
    }
    # given a first access, returns the second access in the stress pattern
    wgsl_stress_second_access = {
        "store": {
            "store": ["{} = i + 1u;".format(wgsl_stress_mem_location)],
            "load": ["let tmp1: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp1 > 100000u) {",
                "  {} = i;".format(wgsl_stress_mem_location),
                "  break;",
                "}"]
        },
        "load": {
            "store": ["{} = i;".format(wgsl_stress_mem_location)],
            "load": ["let tmp2: u32 = {};".format(wgsl_stress_mem_location),
                "if (tmp2 > 100000u) {",
                "  {} = i;".format(wgsl_stress_mem_location),
                "  break;",
                "}"]
        }
    }

    def file_ext(self):
        return ".wgsl"

    def generate_mem_loc(self, variable, mem_loc):
        return "  let a{} = &test_data.value[mem_locations.value[{}]];".format(variable, mem_loc)

    def generate_thread_header(self, workgroup, local_id, has_barrier):
        statements = [
            "if (pre_stress == 1u) {",
            "  do_stress(stress_params.value[5], stress_params.value[6], workgroup_id[0]);",
            "}",
            "if (do_barrier == 1u) {",
            "  spin();",
            "}"
        ]
        if has_barrier:
          to_return = ["if (global_id == u32(workgroupXSize) * {}u + {}u) {{".format(workgroup, local_id)]
          to_return += ["  {}".format(statement) for statement in statements]
          to_return += ["}"]
          return to_return
        else:
          return statements

    def generate_types(self):
        atomic_type = ["[[block]] struct AtomicMemory {", "  value: array<atomic<u32>>;", "};"]
        normal_type = ["[[block]] struct Memory {", "  value: array<u32>;", "};"]
        stress_params_type = ["[[block]] struct StressParamsMemory {", "  value: [[stride(16)]] array<u32, 7>;", "};"]
        return "\n".join(atomic_type + normal_type + stress_params_type)

    def generate_bindings(self):
        bindings = [
            "[[group(0), binding(0)]] var<storage, read_write> test_data : AtomicMemory;",
            "[[group(0), binding(1)]] var<storage, read_write> atomic_test_data : AtomicMemory;",
            "[[group(0), binding(2)]] var<storage, read_write> mem_locations : Memory;",
            "[[group(0), binding(3)]] var<storage, read_write> results : Memory;",
            "[[group(0), binding(4)]] var<storage, read_write> shuffled_ids : Memory;",
            "[[group(0), binding(5)]] var<storage, read_write> barrier : AtomicMemory;",
            "[[group(0), binding(6)]] var<storage, read_write> scratchpad : Memory;",
            "[[group(0), binding(7)]] var<storage, read_write> scratch_locations : Memory;",
            "[[group(0), binding(8)]] var<uniform> stress_params : Memory;"
        ]
        return "\n".join(bindings)

    def generate_meta(self):
        return "\n\n".join([self.generate_types(), self.generate_bindings()])

    def generate_stress(self):
        body = [
            "fn do_stress(iterations: u32, pattern: u32, workgroup_id: u32) {",
            "let addr = scratch_locations.value[workgroup_id];",
            "switch(pattern) {"
        ]
        i = 0
        for first in self.wgsl_stress_first_access:
            for second in self.wgsl_stress_second_access[first]:
                body += [
                    "  case {}u: {{".format(i),
                    "    for(var i: u32 = 0u; i < iterations; i = i + 1u) {"]
                body += ["      {}".format(statement) for statement in self.wgsl_stress_first_access[first]]
                body += ["      {}".format(statement) for statement in self.wgsl_stress_second_access[first][second]]
                body += ["    }", "  }"]
                i += 1
        body += ["  default: {", "    break;", "  }"]
        body += ["}"]
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
            "    bar_val = atomicAdd(&barrier.value[0], 0u);",
            "    i = i + 1u;",
            "  }",
            "}"
        ]
        return "\n".join(body)

    def read_repr(self, instr, workgroup, local_id, has_barrier):
        if instr.use_rmw:
            template = "atomicAdd(a{}, 0u);"
        else:
            template = "atomicLoad(a{});"
        full_instr = template.format(instr.mem_loc)
        if has_barrier:
            statements = [
                "var {}: u32;".format(instr.variable),
                "if (global_id == u32(workgroupXSize) * {}u + {}u) {{".format(workgroup, local_id),
                "  {} = {};".format(instr.variable, full_instr),
                "}"
            ]
            return statements
        else:
            return ["let {} = {};".format(instr.variable, full_instr)]

    def write_repr(self, instr, workgroup, local_id, has_barrier):
        if instr.use_rmw:
            template = "let unused = atomicExchange(a{}, {}u);"
        else:
            template = "atomicStore(a{}, {}u);"
        full_instr = template.format(instr.mem_loc, instr.value)
        if has_barrier:
            statements = [
                "if (global_id == u32(workgroupXSize) * {}u + {}u) {{".format(workgroup, local_id),
                "  " + full_instr,
                "}"
            ]
            return statements
        else:
            return [full_instr]

    def fence_repr(self, instr):
        pass

    def barrier_repr(self, instr):
        if instr.storage_type == "storage":
            return ["storageBarrier();"]
        elif instr.storage_type == "workgroup":
            return ["workgroupBarier();"]

    def results_repr(self, variable):
        return "results.value[{}] = {};".format(self.variables[variable], variable)

    def thread_filter(self, first_thread, workgroup, local_id, has_barrier):
        if first_thread:
            start = "if"
        else:
            start = "} elseif"
        if has_barrier:
          filter = " (global_id >= u32(workgroupXSize) * {}u && global_id < ({}u + 1u)*u32(workgroupXSize)) {{".format(workgroup, workgroup)
        else:
          filter = " (global_id == u32(workgroupXSize) * {}u + {}u) {{".format(workgroup, local_id)
        return start + filter

    def generate_stress_call(self):
        return [
            "  } elseif (stress_params.value[1] == 1u) {",
            "    do_stress(stress_params.value[2], stress_params.value[3], workgroup_id[0]);",
            "  }"
        ]

    def generate_shader_def(self):
        return "\n".join([
            "let workgroupXSize = 1;",
            "[[stage(compute), workgroup_size(workgroupXSize)]] fn main([[builtin(workgroup_id)]] workgroup_id : vec3<u32>, [[builtin(global_invocation_id)]] global_invocation_id : vec3<u32>, [[builtin(local_invocation_index)]] local_invocation_index : u32) {",
            "  let pre_stress = stress_params.value[4];",
            "  let do_barrier = stress_params.value[0];",
            "  let global_id = shuffled_ids.value[global_invocation_id[0]];"
        ])
