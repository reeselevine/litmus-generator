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

    def generate_mem_loc(self, mem_loc, i, offset):
        if offset == 0:
            base = "id_{}".format(i);
            offset_template = ""
        else:
            base = "permute_id(id_{}, stress_params.permute_second, total_ids)".format(i)
            if offset == 1:
                offset_template = " + stress_params.location_offset"
            else:
                offset_template = " + {}u * stress_params.location_offset".format(offset)
        return "let {}_{} = &test_locations.value[{} * stress_params.mem_stride * 2u{}];".format(mem_loc, i, base, offset_template)

    def generate_threads_header(self, test_mem_locs):
        new_local_id = "let local_id_1 = permute_id(local_invocation_id[0], stress_params.permute_first, u32(workgroupXSize));"
        if self.same_workgroup:
            ids = [
                "let total_ids = u32(workgroupXSize);",
                "let id_0 = local_invocation_id[0];",
                new_local_id,
                "let id_1 = local_id_1;"
            ]
            spin = "  spin(u32(workgroupXSize));"
        else:
            ids = [
                "let total_ids = u32(workgroupXSize) * stress_params.testing_workgroups;",
                "let id_0 = shuffled_workgroup * u32(workgroupXSize) + local_invocation_id[0];",
                "let new_workgroup = stripe_workgroup(shuffled_workgroup, local_invocation_id[0]);",
                new_local_id,
                "let id_1 = new_workgroup * u32(workgroupXSize) + local_id_1;"
            ]
            spin = "  spin(u32(workgroupXSize) * stress_params.testing_workgroups);"
        statements = [
            "if (stress_params.pre_stress == 1u) {",
            "  do_stress(stress_params.pre_stress_iterations, stress_params.pre_stress_pattern, shuffled_workgroup);",
            "}",
            "if (stress_params.do_barrier == 1u) {",
            spin,
            "}"
        ]
        return ids + test_mem_locs + statements

    def generate_result_type(self):
        statements = ["[[block]] struct TestResults {"]
        for behavior in self.behaviors:
            statements.append("  {}: atomic<u32>;".format(behavior.key))
        statements.append("};")
        return statements

    def generate_types(self):
        results_type = "\n".join(self.generate_result_type())
        atomic_type = "\n".join(["[[block]] struct AtomicMemory {", "  value: array<atomic<u32>>;", "};"])
        normal_type = "\n".join(["[[block]] struct Memory {", "  value: array<u32>;", "};"])
        stress_params_type = "\n".join([
            "[[block]] struct StressParamsMemory {",
            "  [[size(16)]] do_barrier: u32;",
            "  [[size(16)]] mem_stress: u32;",
            "  [[size(16)]] mem_stress_iterations: u32;",
            "  [[size(16)]] mem_stress_pattern: u32;",
            "  [[size(16)]] pre_stress: u32;",
            "  [[size(16)]] pre_stress_iterations: u32;",
            "  [[size(16)]] pre_stress_pattern: u32;",
            "  [[size(16)]] permute_first: u32;",
            "  [[size(16)]] permute_second: u32;",
            "  [[size(16)]] testing_workgroups: u32;",
            "  [[size(16)]] mem_stride: u32;",
            "  [[size(16)]] location_offset: u32;",
            "};"
        ])
        return "\n\n".join([results_type, atomic_type, normal_type, stress_params_type])

    def generate_bindings(self):
        bindings = [
            "[[group(0), binding(0)]] var<storage, read_write> test_locations : AtomicMemory;",
            "[[group(0), binding(1)]] var<storage, read_write> results : TestResults;",
            "[[group(0), binding(2)]] var<storage, read_write> shuffled_workgroups : Memory;",
            "[[group(0), binding(3)]] var<storage, read_write> barrier : AtomicMemory;",
            "[[group(0), binding(4)]] var<storage, read_write> scratchpad : Memory;",
            "[[group(0), binding(5)]] var<storage, read_write> scratch_locations : Memory;",
            "[[group(0), binding(6)]] var<uniform> stress_params : StressParamsMemory;"
        ]
        return "\n".join(bindings)

    def generate_helper_fns(self):
        permute_fn = [
            "fn permute_id(id: u32, factor: u32, mask: u32) -> u32 {",
            "  return (id * factor) % mask;",
            "}",
            ""
        ]
        stripe_fn = [
            "fn stripe_workgroup(workgroup_id: u32, local_id: u32) -> u32 {",
            "  return (workgroup_id + 1u + local_id % (stress_params.testing_workgroups - 1u)) % stress_params.testing_workgroups;",
            "}"
        ]
        return "\n".join(permute_fn + stripe_fn)

    def generate_meta(self):
        return "\n\n".join([self.generate_types(), self.generate_bindings(), self.generate_helper_fns()])

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
            "fn spin(limit: u32) {",
            "  var i : u32 = 0u;",
            "  var bar_val : u32 = atomicAdd(&barrier.value[0], 1u);",
            "  loop {",
            "    if (i == 1024u || bar_val >= limit) {",
            "      break;",
            "    }",
            "    bar_val = atomicAdd(&barrier.value[0], 0u);",
            "    i = i + 1u;",
            "  }",
            "}"
        ]
        return "\n".join(body)

    def read_repr(self, instr, i):
        if instr.use_rmw:
            template = "let {} = atomicAdd({}_{}, 0u);"
        else:
            template = "let {} = atomicLoad({}_{});"
        return template.format(instr.variable, instr.mem_loc, i)

    def write_repr(self, instr, i):
        if instr.use_rmw:
            template = "let unused = atomicExchange({}_{}, {}u);"
        else:
            template = "atomicStore({}_{}, {}u);"
        return template.format(instr.mem_loc, i, instr.value)

    def fence_repr(self, instr):
        pass

    def barrier_repr(self, instr):
        if instr.storage_type == "storage":
            return "storageBarrier();"
        elif instr.storage_type == "workgroup":
            return "workgroupBarier();"

    def generate_stress_call(self):
        return [
            "  } elseif (stress_params.mem_stress == 1u) {",
            "    do_stress(stress_params.mem_stress_iterations, stress_params.mem_stress_pattern, shuffled_workgroup);",
            "  }"
        ]

    def generate_shader_def(self):
        return "\n".join([
            "let workgroupXSize = 256;",
            "[[stage(compute), workgroup_size(workgroupXSize)]] fn main(",
            "  [[builtin(local_invocation_id)]] local_invocation_id : vec3<u32>,",
            "  [[builtin(workgroup_id)]] workgroup_id : vec3<u32>) {",
            "  let shuffled_workgroup = shuffled_workgroups.value[workgroup_id[0]];",
            "  if (shuffled_workgroup < stress_params.testing_workgroups) {"
        ])

    def generate_post_condition(self, condition):
        if isinstance(condition, self.PostConditionLeaf):
            template = ""
            if condition.output_type == "variable":
                template = "{} == {}u"
            elif condition.output_type == "memory":
                template = "atomicLoad(&test_locations.value[{}_1]) == {}u"
            return template.format(condition.identifier, condition.value)
        elif isinstance(condition, self.PostConditionNode):
            if condition.operator == "and":
                return "(" + " && ".join([self.generate_post_condition(cond) for cond in condition.conditions]) + ")"

    def generate_result_storage(self, behaviors):
        if self.same_workgroup:
            statements = ["workgroupBarrier();"]
        else:
            statements = ["storageBarrier();"]
        first_behavior = True
        for behavior in behaviors:
            condition = self.generate_post_condition(behavior.post_condition)
            if first_behavior:
                template = "if ({}) {{"
            else:
                template = "}} elseif ({}) {{"
            statements.append(template.format(condition))
            statements.append("  atomicAdd(&results.{}, 1u);".format(behavior.key))
            first_behavior = False
        statements.append("}")
        return statements
