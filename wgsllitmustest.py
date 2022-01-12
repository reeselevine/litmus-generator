import litmustest

class WgslLitmusTest(litmustest.LitmusTest):

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

    def generate_mem_loc(self, mem_loc, i, offset, should_shift, workgroup_id="shuffled_workgroup", use_local_id=False):
        shift_mem_loc = ""
        if should_shift:
            shift_mem_loc = "{} * u32(workgroupXSize) + ".format(workgroup_id)
        if offset == 0:
            base = "{}id_{}".format(shift_mem_loc, i);
            offset_template = ""
        else:
            if use_local_id:
                to_permute = "local_invocation_id[0]"
            else:
                to_permute = "id_{}".format(i)
            base = "{}permute_id({}, stress_params.permute_second, total_ids)".format(shift_mem_loc, to_permute)
            if offset == 1:
                offset_template = " + stress_params.location_offset"
            else:
                offset_template = " + {}u * stress_params.location_offset".format(offset)
        return "let {}_{} = ({}) * stress_params.mem_stride * 2u{};".format(mem_loc, i, base, offset_template)

    def generate_threads_header(self, test_mem_locs):
        new_local_id = "permute_id(local_invocation_id[0], stress_params.permute_first, u32(workgroupXSize))"
        suffix = []
        if len(self.threads) > 1:
            if self.same_workgroup:
                suffix = ["let id_1 = {}".format(new_local_id)]
            else:
                suffix = [
                    "let new_workgroup = stripe_workgroup(shuffled_workgroup, local_invocation_id[0]);",
                    "let id_1 = new_workgroup * u32(workgroupXSize) + {};".format(new_local_id)
                ]
        if self.same_workgroup:
            prefix = [
                "let total_ids = u32(workgroupXSize);",
                "let id_0 = local_invocation_id[0];"
            ]
            spin = "  spin(u32(workgroupXSize));"
        else:
            prefix = [
                "let total_ids = u32(workgroupXSize) * stress_params.testing_workgroups;",
                "let id_0 = shuffled_workgroup * u32(workgroupXSize) + local_invocation_id[0];"
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
        return prefix + suffix + test_mem_locs + statements

    def generate_read_result_type(self):
        return [
            "struct ReadResult {",
            "  r0: atomic<u32>;",
            "  r1: atomic<u32>;",
            "};"
        ]

    def generate_test_result_type(self):
        statements = ["[[block]] struct TestResults {"]
        for behavior in self.behaviors:
            statements.append("  {}: atomic<u32>;".format(behavior.key))
        statements.append("};")
        return statements

    def generate_stress_params_type(self):
        return [
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
        ]

    def generate_common_types(self):
        atomic_type = "\n".join(["[[block]] struct AtomicMemory {", "  value: array<atomic<u32>>;", "};"])
        read_result_type = "\n".join(self.generate_read_result_type())
        read_results_type = "\n".join(["[[block]] struct ReadResults {", "  value: array<ReadResult>;", "};"])
        stress_params_type = "\n".join(self.generate_stress_params_type())
        return [atomic_type, read_result_type, read_results_type, stress_params_type]

    def generate_types(self):
        normal_type = "\n".join(["[[block]] struct Memory {", "  value: array<u32>;", "};"])
        return "\n\n".join([normal_type] + self.generate_common_types())

    def generate_result_types(self):
        test_result_type = "\n".join(self.generate_test_result_type())
        return "\n\n".join([test_result_type] + self.generate_common_types())

    def generate_bindings(self):
        bindings = [
            "[[group(0), binding(0)]] var<storage, read_write> test_locations : AtomicMemory;",
            "[[group(0), binding(1)]] var<storage, read_write> results : ReadResults;",
            "[[group(0), binding(2)]] var<storage, read_write> shuffled_workgroups : Memory;",
            "[[group(0), binding(3)]] var<storage, read_write> barrier : AtomicMemory;",
            "[[group(0), binding(4)]] var<storage, read_write> scratchpad : Memory;",
            "[[group(0), binding(5)]] var<storage, read_write> scratch_locations : Memory;",
            "[[group(0), binding(6)]] var<uniform> stress_params : StressParamsMemory;"
        ]
        if self.workgroup_memory:
            bindings += ["", "var<workgroup> wg_test_locations: array<atomic<u32>, 3584>;"]
        return "\n".join(bindings)

    def generate_result_bindings(self):
        return "\n".join([
            "[[group(0), binding(0)]] var<storage, read_write> test_locations : AtomicMemory;",
            "[[group(0), binding(1)]] var<storage, read_write> read_results : ReadResults;",
            "[[group(0), binding(2)]] var<storage, read_write> test_results : TestResults;",
            "[[group(0), binding(3)]] var<uniform> stress_params : StressParamsMemory;"
        ])

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

    def generate_result_meta(self):
        return "\n\n".join([self.generate_result_types(), self.generate_result_bindings(), self.generate_helper_fns()])

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
        if self.workgroup_memory:
            loc = "wg_test_locations"
        else:
            loc = "test_locations.value"
        if instr.use_rmw:
            template = "let {} = atomicAdd(&{}[{}_{}], 0u);"
        else:
            template = "let {} = atomicLoad(&{}[{}_{}]);"
        return template.format(instr.variable, loc, instr.mem_loc, i)

    def write_repr(self, instr, i):
        if self.workgroup_memory:
            loc = "wg_test_locations"
        else:
            loc = "test_locations.value"
        if instr.use_rmw:
            template = "let unused = atomicExchange(&{}[{}_{}], {}u);"
        else:
            template = "atomicStore(&{}[{}_{}], {}u);"
        return template.format(loc, instr.mem_loc, i, instr.value)

    def fence_repr(self, instr):
        pass

    def barrier_repr(self, instr):
        if self.workgroup_memory:
            return "workgroupBarrier();"
        else:
            return "storageBarrier();"

    def results_repr(self, variable, i):
        if self.same_workgroup:
            shift_mem_loc = "shuffled_workgroup * u32(workgroupXSize) + "
        else:
            shift_mem_loc = ""
        return "atomicStore(&results.value[{}id_{}].{}, {});".format(shift_mem_loc, i, variable, variable)

    def generate_stress_call(self):
        return [
            "  } elseif (stress_params.mem_stress == 1u) {",
            "    do_stress(stress_params.mem_stress_iterations, stress_params.mem_stress_pattern, shuffled_workgroup);",
            "  }"
        ]

    def generate_common_shader_def(self):
      return [
          "let workgroupXSize = 256;",
          "[[stage(compute), workgroup_size(workgroupXSize)]] fn main(",
          "  [[builtin(local_invocation_id)]] local_invocation_id : vec3<u32>,",
          "  [[builtin(workgroup_id)]] workgroup_id : vec3<u32>) {"
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

    def generate_result_shader_def(self):
        if self.same_workgroup:
            total_ids = "  let total_ids = u32(workgroupXSize);"
        else:
            total_ids = "  let total_ids = u32(workgroupXSize) * stress_params.testing_workgroups;"
        return "\n".join(self.generate_common_shader_def() + [
          total_ids,
          "  let id_0 = workgroup_id[0] * u32(workgroupXSize) + local_invocation_id[0];"
        ])

    def generate_post_condition(self, condition):
        if isinstance(condition, self.PostConditionLeaf):
            template = ""
            if condition.output_type == "variable":
                template = "{} == {}u"
            elif condition.output_type == "memory":
                template = "mem_{}_0 == {}u"
            return template.format(condition.identifier, condition.value)
        elif isinstance(condition, self.PostConditionNode):
            if condition.operator == "and":
                return "(" + " && ".join([self.generate_post_condition(cond) for cond in condition.conditions]) + ")"

    def generate_result_storage(self):
        statements = ["workgroupBarrier();"]
        seen_ids = set()
        for behavior in self.behaviors:
            statements += self.generate_post_condition_stores(behavior.post_condition, seen_ids)
        return statements

    def generate_post_condition_stores(self, condition, seen_ids):
        result = []
        shift_mem_loc = "shuffled_workgroup * u32(workgroupXSize)"
        if isinstance(condition, self.PostConditionLeaf):
            if condition.identifier not in seen_ids:
                seen_ids.add(condition.identifier)
                if condition.output_type == "variable":
                    variable = condition.identifier
                    if self.same_workgroup:
                        shift = "{} + ".format(shift_mem_loc)
                    else:
                        shift = ""
                    result.append("atomicStore(&results.value[{}id_{}].{}, {});".format(shift, self.read_threads[variable], variable, variable))
                elif condition.output_type == "memory" and self.workgroup_memory:
                    mem_loc = "{}_{}".format(condition.identifier, len(self.threads) - 1)
                    result.append("atomicStore(&test_locations.value[{} * stress_params.mem_stride * 2u + {}], atomicLoad(&wg_test_locations[{}]));".format(shift_mem_loc, mem_loc, mem_loc))
        elif isinstance(condition, self.PostConditionNode):
            for cond in condition.conditions:
                result += self.generate_post_condition_stores(cond, seen_ids)
        return result


    def generate_post_condition_loads(self, condition, seen_ids):
        result = []
        if isinstance(condition, self.PostConditionLeaf):
            if condition.identifier not in seen_ids:
                seen_ids.add(condition.identifier)
                if condition.output_type == "variable":
                    result.append("let {} = atomicLoad(&read_results.value[id_0].{});".format(condition.identifier, condition.identifier))
                elif condition.output_type == "memory":
                    shift = False
                    use_local_id = False
                    if self.same_workgroup:
                        use_local_id = True
                        if self.variable_offsets[condition.identifier] > 0:
                            shift = True
                    result.append(self.generate_mem_loc(condition.identifier, 0, self.variable_offsets[condition.identifier], shift, "workgroup_id[0]", use_local_id))
                    var = "{}_0".format(condition.identifier)
                    result.append("let mem_{} = atomicLoad(&test_locations.value[{}]);".format(var, var))
        elif isinstance(condition, self.PostConditionNode):
            for cond in condition.conditions:
                result += self.generate_post_condition_loads(cond, seen_ids)
        return result

    def generate_result_shader_body(self):
        first_behavior = True
        statements = []
        seen_ids = set()
        for behavior in self.behaviors:
            statements += self.generate_post_condition_loads(behavior.post_condition, seen_ids)
        for behavior in self.behaviors:
            condition = self.generate_post_condition(behavior.post_condition)
            if first_behavior:
                template = "if ({}) {{"
            else:
                template = "}} elseif ({}) {{"
            statements.append(template.format(condition))
            statements.append("  atomicAdd(&test_results.{}, 1u);".format(behavior.key))
            first_behavior = False
        statements.append("}")
        return statements
