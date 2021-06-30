import sys
import os
import argparse
import json
import subprocess

class LitmusTest:

    DEFAULT_LOCAL_ID = 0
    DEFAULT_MEM_ORDER = "relaxed"
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

    class StressAccessPattern:
        
        stress_mem_location = "scratchpad[scratch_locations[get_group_id(0)]]"

        # Returns the first access in the stress pattern
        stress_first_access = {
            "store": ["{} = i;".format(stress_mem_location)],
            "load": ["uint tmp1 = {};".format(stress_mem_location), 
                "if (tmp1 > 100) {", "{} = get_local_id(0);".format(stress_mem_location), 
                "}"]
        }

        # Given a first access, returns the second access in the stress pattern
        stress_second_access = {
            "store": {
                "store": ["{} = i + 1;".format(stress_mem_location)],
                "load": ["uint tmp1 = {};".format(stress_mem_location),
                    "if (tmp1 > 100) {", "break;",
                    "}"]
            },
            "load": {
                "store": ["{} = i;".format(stress_mem_location)],
                "load": ["uint tmp2 = {};".format(stress_mem_location),
                    "if (tmp2 > 100) {", "break;",
                    "}"]
            }
        }

        def __init__(self, pattern):
            self.access_pattern = self.stress_first_access[pattern[0]] + self.stress_second_access[pattern[0]][pattern[1]]

        def pattern(self):
            return self.access_pattern

    class PostCondition:

        def __init__(self, output_type, identifier, value):
            self.output_type = output_type
            self.identifier = identifier
            self.value = value

    class Instruction:

        openCL_mem_order = {
            "relaxed": "memory_order_relaxed",
            "sc": "memory_order_seq_cst",
            "acquire": "memory_order_acquire",
            "release": "memory_order_release",
            "acq_rel": "memory_order_acq_rel"
        }

        def openCl_repr(self):
            pass

    class ReadInstruction(Instruction):

        def __init__(self, mem_loc, variable, mem_order):
            self.mem_loc = mem_loc
            self.variable = variable
            self.mem_order = mem_order

        def openCL_repr(self):
            return "uint {} = atomic_load_explicit(&test_data[{}], {});".format(self.variable, self.mem_loc, self.openCL_mem_order[self.mem_order])

    class WriteInstruction(Instruction):

        def __init__(self, mem_loc, value, mem_order):
            self.mem_loc = mem_loc
            self.value = value
            self.mem_order = mem_order

        def openCL_repr(self):
            return "atomic_store_explicit(&test_data[{}], {}, {});".format(self.mem_loc, self.value, self.openCL_mem_order[self.mem_order])

    class MemoryFence(Instruction):

        def __init__(self, mem_order):
            self.mem_order = mem_order

        def openCL_repr(self):
            return "atomic_work_item_fence(CLK_GLOBAL_MEM_FENCE, {}, memory_scope_device);".format(self.openCL_mem_order[self.mem_order])

    class Thread:
        def __init__(self, workgroup, local_id, instructions):
            self.workgroup = workgroup
            self.local_id = local_id
            self.instructions = instructions

    def __init__(self, test_config, parameter_config):
        self.test_config = test_config
        self.parameter_config = parameter_config
        self.memory_locations = {}
        self.variables = {}
        self.threads = []
        self.post_conditions = []
        self.test_name = test_config['testName']
        self.initialize_threads()
        self.initialize_post_conditions()
        self.initialize_stress_settings()

    # Code below this line initializes settings

    def initialize_stress_settings(self):
        self.pre_stress_pattern = self.StressAccessPattern(self.parameter_config["preStressPattern"])
        self.stress_pattern = self.StressAccessPattern(self.parameter_config["stressPattern"])

    def initialize_threads(self):
        mem_loc = 0
        variable_output = 0
        for thread in self.test_config['threads']:
            instructions = []
            for instruction in thread['actions']:
                if 'memoryLocation' in instruction and instruction['memoryLocation'] not in self.memory_locations:
                    self.memory_locations[instruction['memoryLocation']] = mem_loc
                    mem_loc += 1
                if 'memoryOrder' in instruction:
                    mem_order = instruction['memoryOrder']
                else:
                    mem_order = self.DEFAULT_MEM_ORDER
                if instruction['action'] == "read":
                    if instruction['variable'] not in self.variables:
                        self.variables[instruction['variable']] = variable_output
                        variable_output += 1
                    instructions.append(self.ReadInstruction(instruction['memoryLocation'], instruction['variable'], mem_order))
                if instruction['action'] == "write":
                    instructions.append(self.WriteInstruction(instruction['memoryLocation'], instruction['value'], mem_order))
                if instruction['action'] == "fence":
                    instructions.append(self.MemoryFence(mem_order))
            if 'localId' in thread:
                local_id = thread['localId']
            else:
                local_id = self.DEFAULT_LOCAL_ID
            self.threads.append(self.Thread(thread['workgroup'], local_id, instructions))

    def initialize_post_conditions(self):
        for post_condition in self.test_config['postConditions']:
            self.post_conditions.append(self.PostCondition(post_condition['type'], post_condition['id'], post_condition['value']))

    # Code below this line generates the actual opencl kernel and vulkan code

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
                thread_statements.append(instr.openCL_repr())
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
