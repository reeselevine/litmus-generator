from litmustest import LitmusTest

class WgslLitmusTest(LitmusTest):

    # Defines common data structures used in memory model test shaders.
    shader_mem_structures = """struct Memory {
  value: array<u32>,
};

struct AtomicMemory {
  value: array<atomic<u32>>,
};

struct ReadResult {
  r0: atomic<u32>,
  r1: atomic<u32>,
};

struct ReadResults {
  value: array<ReadResult>,
};

struct StressParamsMemory {
  do_barrier: u32,
  mem_stress: u32,
  mem_stress_iterations: u32,
  mem_stress_pattern: u32,
  pre_stress: u32,
  pre_stress_iterations: u32,
  pre_stress_pattern: u32,
  permute_first: u32,
  permute_second: u32,
  testing_workgroups: u32,
  mem_stride: u32,
  location_offset: u32,
};
"""

    # Structure to hold the counts of occurrences of the possible behaviors of a two-thread, four-instruction test.
    # "seq0" means the first invocation's instructions are observed to have occurred before the second invocation's instructions.
    # "seq1" means the second invocation's instructions are observed to have occurred before the first invocation's instructions.
    # "interleaved" means there was an observation of some interleaving of instructions between the two invocations.
    # "weak" means there was an observation of some ordering of instructions that is inconsistent with the WebGPU memory model.
    four_behavior_test_result_struct = """struct TestResults {
  seq0: atomic<u32>,
  seq1: atomic<u32>,
  interleaved: atomic<u32>,
  weak: atomic<u32>,
};

"""

    # Defines the possible behaviors of a two instruction test. Used to test the behavior of non-atomic memory with barriers and
    # one-thread coherence tests.
    # "seq" means that the expected, sequential behavior occurred.
    # "weak" means that an unexpected, inconsistent behavior occurred.
    two_behavior_test_result_struct = """struct TestResults {
  seq: atomic<u32>,
  weak: atomic<u32>,
};

"""

    # Common bindings used in the test shader phase of a test.
    common_test_shader_bindings = """
@group(0) @binding(1) var<storage, read_write> results : ReadResults;
@group(0) @binding(2) var<storage, read> shuffled_workgroups : Memory;
@group(0) @binding(3) var<storage, read_write> barrier : AtomicMemory;
@group(0) @binding(4) var<storage, read_write> scratchpad : Memory;
@group(0) @binding(5) var<storage, read_write> scratch_locations : Memory;
@group(0) @binding(6) var<uniform> stress_params : StressParamsMemory;
"""

    atomic_test_shader_bindings = common_test_shader_bindings + "@group(0) @binding(0) var<storage, read_write> test_locations : AtomicMemory;"

    non_atomic_test_shader_bindings = common_test_shader_bindings + "@group(0) @binding(0) var<storage, read_write> test_locations : Memory;"

    result_shader_bindings = """
@group(0) @binding(0) var<storage, read_write> test_locations : AtomicMemory;
@group(0) @binding(1) var<storage, read_write> read_results : ReadResults;
@group(0) @binding(2) var<storage, read_write> test_results : TestResults;
@group(0) @binding(3) var<uniform> stress_params : StressParamsMemory;"""

    atomic_workgroup_memory = "var<workgroup> wg_test_locations: array<atomic<u32>, 3584>;"

    non_atomic_workgroup_memory = "var<workgroup> wg_test_locations: array<u32, 3584>;"

    memory_location_fns = """

fn permute_id(id: u32, factor: u32, mask: u32) -> u32 {
   return (id * factor) % mask;
 }

 fn stripe_workgroup(workgroup_id: u32, local_id: u32) -> u32 {
   return (workgroup_id + 1u + local_id % (stress_params.testing_workgroups - 1u)) % stress_params.testing_workgroups;
 }
"""

    test_shader_fns = """
fn spin(limit: u32) {
  var i : u32 = 0u;
  var bar_val : u32 = atomicAdd(&barrier.value[0], 1u);
  loop {
    if (i == 1024u || bar_val >= limit) {
      break;
    }
    bar_val = atomicAdd(&barrier.value[0], 0u);
    i = i + 1u;
  }
}

fn do_stress(iterations: u32, pattern: u32, workgroup_id: u32) {
  let addr = scratch_locations.value[workgroup_id];
  switch(pattern) {
    case 0u: {
      for(var i: u32 = 0u; i < iterations; i = i + 1u) {
        scratchpad.value[addr] = i;
        scratchpad.value[addr] = i + 1u;
      }
    }
    case 1u: {
      for(var i: u32 = 0u; i < iterations; i = i + 1u) {
        scratchpad.value[addr] = i;
        let tmp1: u32 = scratchpad.value[addr];
        if (tmp1 > 100000u) {
          scratchpad.value[addr] = i;
          break;
        }
      }
    }
    case 2u: {
      for(var i: u32 = 0u; i < iterations; i = i + 1u) {
        let tmp1: u32 = scratchpad.value[addr];
        if (tmp1 > 100000u) {
          scratchpad.value[addr] = i;
          break;
        }
        scratchpad.value[addr] = i;
      }
    }
    case 3u: {
      for(var i: u32 = 0u; i < iterations; i = i + 1u) {
        let tmp1: u32 = scratchpad.value[addr];
        if (tmp1 > 100000u) {
          scratchpad.value[addr] = i;
          break;
        }
        let tmp2: u32 = scratchpad.value[addr];
        if (tmp2 > 100000u) {
          scratchpad.value[addr] = i;
          break;
        }
      }
    }
    default: {
    }
  }
}
"""

    shader_entry_point = """
let workgroupXSize = 256u;
@stage(compute) @workgroup_size(workgroupXSize) fn main(
  @builtin(local_invocation_id) local_invocation_id : vec3<u32>,
  @builtin(workgroup_id) workgroup_id : vec3<u32>) {"""

    test_shader_common_header = """
  let shuffled_workgroup = shuffled_workgroups.value[workgroup_id[0]];
  if (shuffled_workgroup < stress_params.testing_workgroups) {"""

    test_shader_common_calculations = """
    let x_0 = ({}id_0) * stress_params.mem_stride * 2u;
    let y_0 = ({}permute_id(id_0, stress_params.permute_second, total_ids)) * stress_params.mem_stride * 2u + stress_params.location_offset;
    let x_1 = ({}id_1) * stress_params.mem_stride * 2u;
    let y_1 = ({}permute_id(id_1, stress_params.permute_second, total_ids)) * stress_params.mem_stride * 2u + stress_params.location_offset;
    if (stress_params.pre_stress == 1u) {{
      do_stress(stress_params.pre_stress_iterations, stress_params.pre_stress_pattern, shuffled_workgroup);
    }}"""

    inter_workgroup_test_shader_code = """
    let total_ids = workgroupXSize * stress_params.testing_workgroups;
    let id_0 = shuffled_workgroup * workgroupXSize + local_invocation_id[0];
    let new_workgroup = stripe_workgroup(shuffled_workgroup, local_invocation_id[0]);
    let id_1 = new_workgroup * workgroupXSize + permute_id(local_invocation_id[0], stress_params.permute_first, workgroupXSize);""" + test_shader_common_calculations.format("", "", "", "") + """
    if (stress_params.do_barrier == 1u) {
      spin(workgroupXSize * stress_params.testing_workgroups);
    }
"""

    intra_workgroup_test_shader_code = """
    let total_ids = workgroupXSize;
    let id_0 = local_invocation_id[0];
    let id_1 = permute_id(local_invocation_id[0], stress_params.permute_first, workgroupXSize);""" + test_shader_common_calculations + """
    if (stress_params.do_barrier == 1u) {{
      spin(workgroupXSize);
    }}
"""

    test_shader_common_footer = """
  } else if (stress_params.mem_stress == 1u) {
    do_stress(stress_params.mem_stress_iterations, stress_params.mem_stress_pattern, shuffled_workgroup);
  }
}
"""

    result_shader_common_calculations = """
  let id_0 = workgroup_id[0] * workgroupXSize + local_invocation_id[0];
  let x_0 = id_0 * stress_params.mem_stride * 2u;
  let mem_x_0 = atomicLoad(&test_locations.value[x_0]);
  let r0 = atomicLoad(&read_results.value[id_0].r0);
  let r1 = atomicLoad(&read_results.value[id_0].r1);"""

    inter_workgroup_result_shader_code = result_shader_common_calculations + """
  let total_ids = workgroupXSize * stress_params.testing_workgroups;
  let y_0 = permute_id(id_0, stress_params.permute_second, total_ids) * stress_params.mem_stride * 2u + stress_params.location_offset;
  let mem_y_0 = atomicLoad(&test_locations.value[y_0]);
"""

    intra_workgroup_result_shader_code = result_shader_common_calculations + """
  let total_ids = workgroupXSize;
  let y_0 = (workgroup_id[0] * workgroupXSize + permute_id(local_invocation_id[0], stress_params.permute_second, total_ids)) * stress_params.mem_stride * 2u + stress_params.location_offset;
  let mem_y_0 = atomicLoad(&test_locations.value[y_0]);
"""

    result_shader_common_footer = """
}
"""

    storage_memory_atomic_test_shader_code = shader_mem_structures + atomic_test_shader_bindings + memory_location_fns + test_shader_fns + shader_entry_point + test_shader_common_header

    storage_memory_non_atomic_test_shader_code = shader_mem_structures + non_atomic_test_shader_bindings + memory_location_fns + test_shader_fns + shader_entry_point + test_shader_common_header

    workgroup_memory_atomic_test_shader_code = shader_mem_structures + atomic_test_shader_bindings + atomic_workgroup_memory + memory_location_fns + test_shader_fns + shader_entry_point + test_shader_common_header

    workgroup_memory_non_atomic_test_shader_code = shader_mem_structures + atomic_test_shader_bindings + non_atomic_workgroup_memory + memory_location_fns + test_shader_fns + shader_entry_point + test_shader_common_header

    result_shader_common_code = shader_mem_structures + result_shader_bindings + memory_location_fns + shader_entry_point

    def build_test_shader(self, test_code):
        mem_type_code = ""
        storage_shift = ""
        if self.memory_type == "atomic_storage":
            mem_type_code = self.storage_memory_atomic_test_shader_code
            storage_shift = "shuffled_workgroup * workgroupXSize + "
        elif self.memory_type == "non_atomic_storage":
            mem_type_code = self.storage_memory_non_atomic_test_shader_code
        elif self.memory_type == "atomic_workgroup":
            mem_type_code = self.workgroup_memory_atomic_test_shader_code
        elif self.memory_type == "non_atomic_workgroup":
            mem_type_code = self.workgroup_memory_non_atomic_test_shader_code
        test_type_code = ""
        if self.test_type == "inter_workgroup":
            test_type_code = self.inter_workgroup_test_shader_code
        elif self.test_type == "intra_workgroup":
            test_type_code = self.intra_workgroup_test_shader_code.format(storage_shift, storage_shift, storage_shift, storage_shift)
        return mem_type_code + test_type_code + test_code + self.test_shader_common_footer

    def build_result_shader(self, result_code):
        result_structure = ""
        if self.num_behaviors == 2:
            result_structure = self.two_behavior_test_result_struct
        elif self.num_behaviors == 4:
            result_structure = self.four_behavior_test_result_struct
        test_type_code = ""
        if self.test_type == "inter_workgroup":
            test_type_code = self.inter_workgroup_result_shader_code
        elif self.test_type == "intra_workgroup":
            test_type_code = self.intra_workgroup_result_shader_code
        return result_structure + self.result_shader_common_code + test_type_code + result_code + self.result_shader_common_footer

    def file_ext(self):
        return ".wgsl"

    def read_repr(self, instr, i):
        if self.memory_type == "atomic_workgroup":
            loc = "wg_test_locations"
        else:
            loc = "test_locations.value"
        if instr.use_rmw:
            template = "let {} = atomicAdd(&{}[{}_{}], 0u);"
        else:
            template = "let {} = atomicLoad(&{}[{}_{}]);"
        return template.format(instr.variable, loc, instr.mem_loc, i)

    def write_repr(self, instr, i):
        if self.memory_type == "atomic_workgroup":
            loc = "wg_test_locations"
        else:
            loc = "test_locations.value"
        if instr.use_rmw:
            template = "atomicExchange(&{}[{}_{}], {}u);"
        else:
            template = "atomicStore(&{}[{}_{}], {}u);"
        return template.format(loc, instr.mem_loc, i, instr.value)

    def fence_repr(self, instr):
        if self.memory_type == "atomic_workgroup":
            return "workgroupBarrier();"
        else:
            return "storageBarrier();"

    def store_read_result_repr(self, variable, i):
        if self.test_type == "intra_workgroup":
            shift_mem_loc = "shuffled_workgroup * workgroupXSize + "
        else:
            shift_mem_loc = ""
        return "atomicStore(&results.value[{}id_{}].{}, {});".format(shift_mem_loc, i, variable, variable)

    def store_workgroup_mem_repr(self, _id):
        if self.test_type == "intra_workgroup":
            shift_mem_loc = "shuffled_workgroup * workgroupXSize * "
        else:
            shift_mem_loc = ""
        mem_loc = "{}_{}".format(_id, len(self.threads) - 1)
        return "atomicStore(&test_locations.value[{}stress_params.mem_stride * 2u + {}], atomicLoad(&wg_test_locations[{}]));".format(shift_mem_loc, mem_loc, mem_loc)

    def post_cond_var_repr(self, condition):
        return "{} == {}u".format(condition.identifier, condition.value)

    def post_cond_mem_repr(self, condition):
        return "mem_{}_0 == {}u".format(condition.identifier, condition.value)

    def post_cond_and_node_repr(self, conditions):
        return "(" + " && ".join(conditions) + ")"

    def generate_behavior_checks(self):
        statements = []
        i = 0
        for behavior in self.behaviors:
            if i == 0:
                template = "if ({}) {{"
            else:
                template = "}} else if ({}) {{"
            statements.append(template.format(self.generate_post_condition(behavior.post_condition)))
            statements.append("  atomicAdd(&test_results.{}, 1u);".format(behavior.key))
            if i == len(self.behaviors) - 1:
                statements.append("}")
            i += 1
        return statements
