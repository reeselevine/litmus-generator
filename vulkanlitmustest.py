import litmustest

class VulkanLitmusTest(litmustest.LitmusTest):

    shader_fn_call = "__kernel void litmus_test ("

    common_test_shader_args = """
  __global atomic_uint* read_results,
  __global uint* shuffled_workgroups,
  __global atomic_uint* barrier,
  __global uint* scratchpad,
  __global uint* scratch_locations,
  __global uint* stress_params
"""

    atomic_test_shader_args = "  __global atomic_uint* test_locations," + common_test_shader_args
    non_atomic_test_shader_args = "  __global uint* test_locations," + common_test_shader_args

    shader_fn_call = "__kernel void litmus_test ("

    result_shader_args = """
  __global atomic_uint* test_locations,
  __global atomic_uint* read_results,
  __global atomic_uint* test_results,
  __global uint* stress_params
"""

    atomic_local_memory = "  __local atomic_uint wg_test_locations[3584];"
    non_atomic_local_memory = "  __local uint wg_test_locations[3584];"

    memory_location_fns = """
static uint permute_id(uint id, uint factor, uint mask) {
  return (id * factor) % mask;
}

static uint stripe_workgroup(uint workgroup_id, uint local_id, uint testing_workgroups) {
  return (workgroup_id + 1 + local_id % (testing_workgroups - 1)) % testing_workgroups;
}
"""

    test_shader_fns = """
static void spin(__global atomic_uint* barrier, uint limit) {
  int i = 0;
  uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);
  while (i < 1024 && val < limit) {
    val = atomic_load_explicit(barrier, memory_order_relaxed);
    i++;
  }
}

static void do_stress(__global uint* scratchpad, __global uint* scratch_locations, uint iterations, uint pattern) {
  for (uint i = 0; i < iterations; i++) {
    if (pattern == 0) {
      scratchpad[scratch_locations[get_group_id(0)]] = i;
      scratchpad[scratch_locations[get_group_id(0)]] = i + 1;
    } else if (pattern == 1) {
      scratchpad[scratch_locations[get_group_id(0)]] = i;
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
    } else if (pattern == 2) {
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
      scratchpad[scratch_locations[get_group_id(0)]] = i;
    } else if (pattern == 3) {
      uint tmp1 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp1 > 100) {
        break;
      }
      uint tmp2 = scratchpad[scratch_locations[get_group_id(0)]];
      if (tmp2 > 100) {
        break;
      }
    }
  }
}
"""

    test_shader_common_header = """
  uint shuffled_workgroup = shuffled_workgroups[get_group_id(0)];
  if(shuffled_workgroup < stress_params[9]) {
"""

    test_shader_common_calculations = """
    uint x_0 = ({}id_0) * stress_params[10] * 2;
    uint y_0 = ({}permute_id(id_0, stress_params[8], total_ids)) * stress_params[10] * 2 + stress_params[11];
    uint x_1 = ({}id_1) * stress_params[10] * 2;
    uint y_1 = ({}permute_id(id_1, stress_params[8], total_ids)) * stress_params[10] * 2 + stress_params[11];
    if (stress_params[4]) {{
      do_stress(scratchpad, scratch_locations, stress_params[5], stress_params[6]);
    }}
"""

    inter_workgroup_test_shader_code = """
    uint total_ids = get_local_size(0) * stress_params[9];
    uint id_0 = shuffled_workgroup * get_local_size(0) + get_local_id(0);
    uint new_workgroup = stripe_workgroup(shuffled_workgroup, get_local_id(0), stress_params[9]);
    uint id_1 = new_workgroup * get_local_size(0) + permute_id(get_local_id(0), stress_params[7], get_local_size(0)); """ + test_shader_common_calculations.format("", "", "", "") + """
    if (stress_params[0]) {
      spin(barrier, get_local_size(0) * stress_params[9]);
    }
"""

    intra_workgroup_test_shader_code = """
    uint total_ids = get_local_size(0);
    uint id_0 = get_local_id(0);
    uint id_1 = permute_id(get_local_id(0), stress_params[7], get_local_size(0));""" + test_shader_common_calculations + """
    if (stress_params[0]) {{
      spin(barrier, get_local_size(0));
    }}
    """

    test_shader_common_footer = """
  } else if (stress_params[1]) {
    do_stress(scratchpad, scratch_locations, stress_params[2], stress_params[3]);
  }
}
"""

    result_shader_common_calculations = """
  uint total_ids = get_local_size(0) * stress_params[9];
  uint id_0 = get_global_id(0);
  uint x_0 = (id_0) * stress_params[10] * 2;
  uint mem_x_0 = atomic_load(&test_locations[x_0]);
  uint r0 = atomic_load(&read_results[id_0 * 2]);
  uint r1 = atomic_load(&read_results[id_0 * 2 + 1]);
"""

    inter_workgroup_result_shader_code = result_shader_common_calculations + """
  uint total_ids = get_local_size(0) * stress_params[9];
  uint y_0 = (permute_id(id_0, stress_params[8], total_ids)) * stress_params[10] * 2 + stress_params[11];
  uint mem_y_0 = atomic_load(&test_locations[y_0]);
"""

    intra_workgroup_result_shader_code = """TODO"""

    result_shader_common_footer = """
}
    """

    global_memory_atomic_test_shader_code = memory_location_fns + test_shader_fns + shader_fn_call + atomic_test_shader_args + test_shader_common_header
    global_memory_non_atomic_test_shader_code = memory_location_fns + test_shader_fns + shader_fn_call + non_atomic_test_shader_args + test_shader_common_header
    local_memory_atomic_test_shader_code = memory_location_fns + test_shader_fns + shader_fn_call + atomic_test_shader_args + atomic_local_memory + test_shader_common_header
    local_memory_non_atomic_test_shader_code = memory_location_fns + test_shader_fns + shader_fn_call + atomic_test_shader_args + non_atomic_local_memory + test_shader_common_header

    result_shader_common_code = memory_locaion_fns + shader_fn_call + result_shader_args

    def build_test_shader(self, test_code):
        mem_type_code = ""
        storage_shift = ""
        if self.memory_type == "atomic_storage":
            mem_type_code = self.global_memory_atomic_test_shader_code
            storage_shift = "shuffled_workgroup * get_local_size(0) + "
        elif self.memory_type == "non_atomic_storage":
            mem_type_code = self.global_memory_non_atomic_test_shader_code
        elif self.memory_type == "atomic_workgroup":
            mem_type_code = self.local_memory_atomic_test_shader_code
        elif self.memory_type == "non_atomic_workgroup":
            mem_type_code = self.local_memory_non_atomic_test_shader_code
        test_type_code = ""
        if self.test_type == "inter_workgroup":
            test_type_code = self.inter_workgroup_test_shader_code
        elif self.test_type == "intra_workgroup":
            test_type_code = self.intra_workgroup_test_shader_code.format(storage_shift, storage_shift, storage_shift, storage_shift)
        return mem_type_code + test_type_code + test_code + self.test_shader_common_footer

    def build_result_shader(self, result_code):
        test_type_code = ""
        if self.test_type == "inter_workgroup":
            test_type_code = self.inter_workgroup_result_shader_code
        elif self.test_type == "intra_workgroup":
            test_type_code = self.intra_workgroup_result_shader_code
        return self.result_shader_common_code + test_type_code + result_code + self.result_shader_common_footer

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

    def read_repr(self, instr, i):
        if self.memory_type = "atomic_workgroup":
            loc = "wg_test_locations"
        else:
            loc = "test_locations"
        if instr.use_rmw:
            template = "uint {} = atomic_fetch_add_explicit(&{}[{}_{}], 0, {});"
        else:
            template = "uint {} = atomic_load_explicit(&{}[{}_{}], {});"
        return template.format(instr.variable, loc, instr.mem_loc, i, self.openCL_mem_order[instr.mem_order])

    def write_repr(self, instr, i):
        if self.memory_type == "atomic_workgroup":
            loc = "wg_test_locations"
        else:
            loc = "test_locations"
        if instr.use_rmw:
            template = "uint unused = atomic_exchange_explicit(&{}[{}_{}], {}, {});"
        else:
            template = "atomic_store_explicit(&{}[{}_{}], {}, {});"
        return template.format(loc, instr.mem_loc, i, instr.value, self.openCL_mem_order[instr.mem_order])

    def fence_repr(self, instr):
        if self.memory_type == "atomic_workgroup":
            return "atomic_work_item_fence(CLK_LOCAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"
        else:
            return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, memory_order_seq_cst, memory_scope_device);"

    def store_read_result_repr(self, variable, i):
        if self.test_type == "intra_workgroup":
            shift_mem_loc = "shuffled_workgroup * get_local_size(0) + "
        else:
            shift_mem_loc = ""
        if variable == "r0":
            result_template = ""
        else:
            result_template = " + 1"
        return "atomic_store(&read_results[{}id_{} * 2{}], {});".format(shift_mem_loc, i, result_template, variable)

    def store_workgroup_mem_repr(self, _id):
        if self.test_type == "intra_workgroup":
            shift_mem_loc = "shuffled_workgroup * get_local_size(0) + "
        else:
            shift_mem_loc = ""
        result.append("atomic_store(&test_locations[{} * stress_params[10] * 2 + {}], atomic_load(&wg_test_locations[{}]));".format(shift_mem_loc, mem_loc, mem_loc))


    def post_cond_var_repr(self, condition):
        return "{} == {}".format(condition.identifier, condition.value)

    def post_cond_mem_repr(self, condition):
        return "mem_{}_0 == {}".format(condition.identifier, condition.value)

    def post_cond_and_node_repr(self, conditions):
        return "(" + " && ".join(conditions) + ")"

    def generate_behavior_check(self, cond, key, first_behavior, last_behavior):
        statements = []
        if first_behavior:
            template = "if ({}) {{"
        else:
            template = "}} else if ({}) {{"
        statements.append(template.format(cond))
        statements.append("  atomic_fetch_add(&test_results[{}], 1);".format(key))
        if last_behavior:
            statements.append("}")
        return statements

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
                template = "mem_{}_0 == {}"
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
                    result.append("atomic_store(&read_results[{}id_{} * 2{}], {});".format(shift, self.read_threads[variable], result_template, variable))
                elif condition.output_type == "memory" and self.workgroup_memory:
                    mem_loc = "{}_{}".format(condition.identifier, len(self.threads) - 1)
                    result.append("atomic_store(&test_locations[{} * stress_params[10] * 2 + {}], atomic_load(&wg_test_locations[{}]));".format(shift_mem_loc, mem_loc, mem_loc))
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
                    result.append("uint mem_{} = atomic_load(&test_locations[{}]);".format(var, var))
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
