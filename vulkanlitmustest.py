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

    def generate_mem_loc(self, mem_loc, i, offset, should_shift, workgroup_id="shuffled_workgroup", use_local_id=False):
        shift_mem_loc = ""
        if should_shift:
            shift_mem_loc = "{} * get_local_size(0) + ".format(workgroup_id)
        if offset == 0:
            base = "{}id_{}".format(shift_mem_loc, i)
            offset_template = ""
        else:
            if use_local_id:
                to_permute = "get_local_id(0)"
            else:
                to_permute = "id_{}".format(i)
            base = "{}permute_id({}, stress_params[8], total_ids)".format(shift_mem_loc, to_permute)
            if offset == 1:
                offset_template = " + stress_params[11]"
            else:
                offset_template = " + {} * stress_params[11]".format(offset)
        return "uint {}_{} = ({}) * stress_params[10] * 2{};".format(mem_loc, i, base, offset_template)

    def generate_threads_header(self, test_mem_locs):
        new_local_id = "permute_id(get_local_id(0), stress_params[7], get_local_size(0))"
        suffix = []
        if len(self.threads) > 1:
            if self.same_workgroup:
                suffix = ["uint id_1 = {};".format(new_local_id)]
            else:
                suffix = [
                    "uint new_workgroup = stripe_workgroup(shuffled_workgroup, get_local_id(0), stress_params[9]);",
                    "uint id_1 = new_workgroup * get_local_size(0) + {};".format(new_local_id)
                ]
        if self.same_workgroup:
            prefix = [
                "uint total_ids = get_local_size(0);",
                "uint id_0 = get_local_id(0);"
            ]
            spin = "  spin(barrier, get_local_size(0));"
        else:
            prefix = [
                "uint total_ids = get_local_size(0) * stress_params[9];",
                "uint id_0 = shuffled_workgroup * get_local_size(0) + get_local_id(0);"
            ]
            spin = "  spin(barrier, get_local_size(0) * stress_params[9]);"
        statements = [
            "if (stress_params[4]) {",
            "  do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);",
            "}",
            "if (stress_params[0]) {",
            spin,
            "}"
        ]
        return prefix + suffix + test_mem_locs + statements

    def generate_helper_fns(self):
        permute_fn = [
            "static uint permute_id(uint id, uint factor, uint mask) {",
            "  return (id * factor) % mask;",
            "}",
            ""
        ]
        stripe_fn = [
            "static uint stripe_workgroup(uint workgroup_id, uint local_id, uint testing_workgroups) {",
            "  return (workgroup_id + 1 + local_id % (testing_workgroups - 1)) % testing_workgroups;",
            "}"
        ]
        return "\n".join(permute_fn + stripe_fn)

    def generate_meta(self):
        return "".join([self.generate_helper_fns()])

    def generate_result_meta(self):
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
        header = "static void spin(__global atomic_uint* barrier, uint limit) {"
        body = "\n  ".join([
            header,
            "int i = 0;",
            "uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
            "while (i < 1024 && val < limit) {",
            "  val = atomic_load_explicit(barrier, memory_order_relaxed);",
            "  i++;",
            "}"
        ])
        return "\n".join([body, "}"])

    def read_repr(self, instr, i):
        if self.workgroup_memory:
            loc = "wg_test_locations"
        else:
            loc = "test_locations"
        if instr.use_rmw:
            template = "uint {} = atomic_fetch_add_explicit(&{}[{}_{}], 0, {});"
        else:
            template = "uint {} = atomic_load_explicit(&{}[{}_{}], {});"
        return template.format(instr.variable, loc, instr.mem_loc, i, self.openCL_mem_order[instr.mem_order])

    def write_repr(self, instr, i):
        if self.workgroup_memory:
            loc = "wg_test_locations"
        else:
            loc = "test_locations"
        if instr.use_rmw:
            template = "uint unused = atomic_exchange_explicit(&{}[{}_{}], {}, {});"
        else:
            template = "atomic_store_explicit(&{}[{}_{}], {}, {});"
        return template.format(loc, instr.mem_loc, i, instr.value, self.openCL_mem_order[instr.mem_order])

    def fence_repr(self, instr):
        if self.workgroup_memory:
            return "atomic_work_item_fence(CLK_LOCAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"
        else:
            return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"
        

    def barrier_repr(self, instr):
        if self.workgroup_memory:
            return "atomic_work_item_fence(CLK_LOCAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"
        else:
            return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"

    def results_repr(self, variable, i):
        if self.same_workgroup:
            shift_mem_loc = "shuffled_workgroup * get_local_size(0) + "
        else:
            shift_mem_loc = ""
        if variable == "r0":
            result_template = ""
        else:
            result_template = " + 1"
        return "atomic_store(&read_results[{}id_{}*2{}], {});".format(shift_mem_loc, i, result_template, variable)

    def generate_stress_call(self):
        return [
            "  } else if (stress_params[1]) {",
            "    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);",
            "  }"
        ]

    def generate_common_shader_def(self):
      return [
            "__kernel void litmus_test(",
            "  __global atomic_uint* test_locations,",
            "  __global atomic_uint* read_results,",
            "  __global atomic_uint* test_results,",
            "  __global uint* stress_params) {",
      ]

    def generate_shader_def(self):
        kernel_header = [
            "__kernel void litmus_test (",
            "  __global atomic_uint* test_locations,",
            "  __global atomic_uint* read_results,",
            "  __global uint* shuffled_workgroups,",
            "  __global atomic_uint* barrier,",
            "  __global uint* scratchpad,",
            "  __global uint* scratch_locations,",
            "  __global uint* stress_params) {",
        ]
        if self.workgroup_memory:
            kernel_header += ["  __local atomic_uint wg_test_locations[3584];"]
        kernel_header += ["  uint shuffled_workgroup = shuffled_workgroups[get_group_id(0)];", "  if(shuffled_workgroup < stress_params[9]) {"]
        return "\n".join(kernel_header)

    def generate_result_shader_def(self):
        # Is total_ids needed?
        if self.same_workgroup:
            total_ids = "  uint total_ids = get_local_size(0);"
        else:
            total_ids = "  uint total_ids = get_local_size(0) * stress_params[9];"
        return "\n".join(self.generate_common_shader_def() + [
          total_ids,
          "  uint id_0 = get_global_id(0);"
        ])

    def generate_post_condition(self, condition):
        if isinstance(condition, self.PostConditionLeaf):
            template = ""
            if condition.output_type == "variable":
                template = "{} == {}"
            elif condition.output_type == "memory":
                template = "mem_{}_0 == {}u"
            return template.format(condition.identifier, condition.value)
        elif isinstance(condition, self.PostConditionNode):
            if condition.operator == "and":
                return "(" + " && ".join([self.generate_post_condition(cond) for cond in condition.conditions]) + ")"

    def generate_result_storage(self):
        statements = []
        seen_ids = set()
        for behavior in self.behaviors:
            statements += self.generate_post_condition_stores(behavior.post_condition, seen_ids)
        return statements

    def generate_post_condition_stores(self, condition, seen_ids):
        result = []
        shift_mem_loc = "shuffled_workgroup * get_local_size(0)"
        if isinstance(condition, self.PostConditionLeaf):
            if condition.identifier not in seen_ids:
                seen_ids.add(condition.identifier)
                if condition.output_type == "variable":
                    variable = condition.identifier
                    if self.same_workgroup:
                        shift = "{} + ".format(shift_mem_loc)
                    else:
                        shift = ""
                    if variable == "r0":
                        result_template = ""
                    else:
                        result_template = " + 1"
                    result.append("atomic_store(&read_results[{}id_{}*2{}], {});".format(shift, self.read_threads[variable], result_template, variable))
                elif condition.output_type == "memory" and self.workgroup_memory:
                    mem_loc = "{}_{}".format(condition.identifier, len(self.threads) - 1)
                    result.append("atomic_store_explicit(&test_locations[{} * stress_params[10] * 2 + {}], atomic_load_explicit(&wg_test_locations[{}]));".format(shift_mem_loc, mem_loc, mem_loc))
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
                    if condition.identifier == "r0":
                        result_template = ""
                    else:
                        result_template = " + 1"
                    result.append("uint {} = atomic_load(&read_results[id_0 * 2{}]);".format(condition.identifier, result_template))
                elif condition.output_type == "memory":
                    shift = False
                    use_local_id = False
                    if self.same_workgroup:
                        use_local_id = True
                        if self.variable_offsets[condition.identifier] > 0:
                            shift = True
                    result.append(self.generate_mem_loc(condition.identifier, 0, self.variable_offsets[condition.identifier], shift, "workgroup_id[0]", use_local_id))
                    var = "{}_0".format(condition.identifier)
                    result.append("uint mem_{} = atomic_load(&test_locations.value[{}]);".format(var, var))
        elif isinstance(condition, self.PostConditionNode):
            for cond in condition.conditions:
                result += self.generate_post_condition_loads(cond, seen_ids)
        return result

    def generate_result_shader_body(self):
        first_behavior = True
        statements = []
        seen_ids = set()
        index = 0
        for behavior in self.behaviors:
            statements += self.generate_post_condition_loads(behavior.post_condition, seen_ids)
        for behavior in self.behaviors:
            condition = self.generate_post_condition(behavior.post_condition)
            if first_behavior:
                template = "if ({}) {{"
            else:
                template = "}} else if ({}) {{"
            statements.append(template.format(condition))
            statements.append("  atomic_fetch_add(&test_results[{}], 1);".format(index))
            first_behavior = False
            index += 1
        statements.append("}")
        return statements
