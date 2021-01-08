import sys
import argparse
import json
import subprocess

mo_relaxed = "memory_order_relaxed"
mo_seq_cst = "memory_order_seq_cst"
DEFAULT_LOCAL_ID = 0
defaults_dict = {
    "numWorkgroups": 4,
    "workgroupSize": 1,
    "shuffle": 0,
    "barrier": 1,
    "memStride": 1,
    "memStress": 1,
    "stressLineSize": 2,
    "stressTargetLines": 1,
    "stressAssignmentStrategy": "ROUND_ROBIN",
    "preStress": 1}

class LitmusTest:

    class StressAccessPattern:

        # Returns the first access in the stress pattern
        stress_first_access = {
            "store": "{} = i;",
            "load": "int tmp1 = {};"
        }

        # Given a first access, returns the second access in the stress pattern
        stress_second_access = {
            "store": {
                "store": "{} = i + 1;",
                "load": "int tmp1 = {};"
            },
            "load": {
                "store": "{} = i;",
                "load": "int tmp2 = {};"
            }
        }

        def __init__(self, pattern):
            stress_mem_location = "scratchpad[scratch_locations[get_group_id(0)]]"
            self.access_pattern = [
                self.stress_first_access[pattern[0]].format(stress_mem_location),
                self.stress_second_access[pattern[0]][pattern[1]].format(stress_mem_location)
            ]

        def pattern(self):
            return self.access_pattern

    class PostCondition:

        def __init__(self, output_type, identifier, value):
            self.output_type = output_type
            self.identifier = identifier
            self.value = value

    class Instruction:

        def openCl_repr(self):
            pass

    class ReadInstruction(Instruction):

        def __init__(self, mem_loc, variable):
            self.mem_loc = mem_loc
            self.variable = variable

        def openCL_repr(self):
            return "uint {} = atomic_load_explicit(&test_data[{}], {});".format(self.variable, self.mem_loc, mo_relaxed)

    class WriteInstruction(Instruction):

        def __init__(self, mem_loc, value):
            self.mem_loc = mem_loc
            self.value = value

        def openCL_repr(self):
            return "atomic_store_explicit(&test_data[{}], {}, {});".format(self.mem_loc, self.value, mo_relaxed)

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
        self.template_replacements = {}
        self.initialize_template_replacements()
        self.initialize_threads()
        self.initialize_post_conditions()
        self.initialize_stress_settings()

    # Code below this line initializes settings

    def initialize_stress_settings(self):
        min_size = self.template_replacements['stressLineSize'] * self.template_replacements['stressTargetLines']
        if 'scratchMemorySize' in self.parameter_config:
            if self.parameter_config['scratchMemorySize'] < min_size:
                raise Exception("scratch memory too small")
            else:
                self.template_replacements['scratchMemorySize'] = self.parameter_config['scratchMemorySize']
        else:
            self.template_replacements['scratchMemorySize'] = min_size
        self.pre_stress_pattern = self.StressAccessPattern(self.parameter_config["preStressPattern"])
        self.stress_pattern = self.StressAccessPattern(self.parameter_config["stressPattern"])

    def initialize_template_replacements(self):
        for key in defaults_dict:
            if key in self.parameter_config:
                self.template_replacements[key] = self.parameter_config[key]
            else:
                self.template_replacements[key] = defaults_dict[key]

    def initialize_threads(self):
        mem_loc = 0
        variable_output = 0
        for thread in self.test_config['threads']:
            instructions = []
            for instruction in thread['actions']:
                if instruction['memoryLocation'] not in self.memory_locations:
                    self.memory_locations[instruction['memoryLocation']] = mem_loc
                    mem_loc += 1
                if instruction['action'] == "read":
                    if instruction['variable'] not in self.variables:
                        self.variables[instruction['variable']] = variable_output
                        variable_output += 1
                    instructions.append(self.ReadInstruction(instruction['memoryLocation'], instruction['variable']))
                if instruction['action'] == "write":
                    instructions.append(self.WriteInstruction(instruction['memoryLocation'], instruction['value']))
            if 'localId' in thread:
                local_id = thread['localId']
            else:
                local_id = DEFAULT_LOCAL_ID
            self.threads.append(self.Thread(thread['workgroup'], local_id, instructions))
        min_test_memory_size = self.template_replacements['memStride'] * len(self.memory_locations)
        if 'testMemorySize' in self.parameter_config:
            if self.parameter_config['testMemorySize'] < min_test_memory_size:
                raise Exception("test memory too small")
            else:
                self.template_replacements['testMemorySize'] = self.parameter_config['testMemorySize']
        else:
            self.template_replacements['testMemorySize'] = min_test_memory_size
        self.template_replacements['numMemLocations'] = len(self.memory_locations)

    def initialize_post_conditions(self):
        num_outputs = 0
        for post_condition in self.test_config['postConditions']:
            if post_condition['type'] == "variable":
                num_outputs += 1
            self.post_conditions.append(self.PostCondition(post_condition['type'], post_condition['id'], post_condition['value']))
        self.template_replacements['numOutputs'] = num_outputs
        conditions = []
        for post_condition in self.post_conditions:
            if post_condition.output_type == "variable":
                conditions.append("output[{}] == {}".format(self.variables[post_condition.identifier], post_condition.value))
            elif post_condition.output_type == "memory":
                conditions.append("data[memLocations[{}]] == {}".format(self.memory_locations[post_condition.identifier], post_condition.value))
        self.template_replacements['postCondition'] = " && ".join(conditions)

    # Code below this line generates the actual opencl kernel and vulkan code

    def generate(self):
        self.generate_openCL_kernel()
        self.generate_vulkan_setup()

    def generate_openCL_kernel(self):
        body_statements = []
        first_thread = True
        for thread in self.threads:
            variables = set()
            thread_statements = [
                "if (pre_stress) {",
                "  for (uint i = 0; i < {}; i++) {{".format(self.parameter_config["preStressIterations"])
            ]
            thread_statements = thread_statements + ["    {}".format(statement) for statement in self.pre_stress_pattern.pattern()]
            thread_statements = thread_statements + ["  }", "}", "if (use_barrier) {", "  spin(barrier);", "}"]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements.append(instr.openCL_repr())
            for variable in variables:
                thread_statements.append("atomic_store_explicit(&results[{}], {}, {});".format(self.variables[variable], variable, mo_seq_cst))
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(thread.workgroup, thread.local_id, first_thread))] + thread_statements
            first_thread = False
        body_statements = body_statements + [self.generate_mem_stress()]
        attribute = "__attribute__ ((reqd_work_group_size({}, 1, 1)))".format(self.template_replacements['workgroupSize'])
        kernel_args = ["__global atomic_uint* test_data", "__global atomic_uint* results", "__global uint* shuffled_ids","__global atomic_uint* barrier", "__global uint* scratchpad", "__global uint* scratch_locations", "int mem_stress", "int pre_stress", "int use_barrier"]
        for location in self.memory_locations:
            kernel_args.append("int {}".format(location))
        kernel_func_def = "__kernel void litmus_test(\n  " + ",\n  ".join(kernel_args) + ") {"
        kernel = "\n".join([attribute, kernel_func_def] + body_statements + ["}\n"])
        spin_func = self.generate_spin()
        kernel = "\n\n".join([spin_func, kernel])
        output_file = open(self.test_name + ".cl", "w")
        output_file.write(kernel)
        output_file.close()

    def generate_spin(self):
        header = "static void spin(__global atomic_uint* barrier) {"
        body = "\n  ".join([
            header,
            "int i = 0;",
            "uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
            "while (i < 1000 && val < {}) {{".format(len(self.threads)),
            "  val = atomic_load_explicit(barrier, memory_order_relaxed);",
            "  i++;",
            "}"
        ])
        return "\n".join([body, "}"])

    def generate_mem_stress(self):
        block = [
            "  } else if (mem_stress) {",
            "  for (uint i = 0; i < {}; i++) {{".format(self.parameter_config["stressIterations"])
        ]
        block = block + ["    {}".format(statement) for statement in self.stress_pattern.pattern()]
        block = block + ["  }", "}"]
        return "\n    ".join(block)

    def thread_filter(self, workgroup, thread, first_thread):
        if first_thread:
            start = "if"
        else:
            start = "} else if"
        return start + " (shuffled_ids[get_global_id(0)] == get_local_size(0) * {} + {}) {{".format(workgroup, thread)

    def spirv_code(self):
        spirv_output = subprocess.check_output(["/home/tyler/Documents/clspv/alan_clspv/clspv/build/bin/clspv", "--cl-std=CL2.0", "--inline-entry-points","-mfmt=c", self.test_name + ".cl", "-o",  "-"])
        decoded_spirv = spirv_output.decode().replace("\n", "")
        spirv_length = decoded_spirv.count(",") + 1
        self.template_replacements["shaderCode"] = spirv_output.decode().replace("\n", "")
        self.template_replacements["shaderSize"] = spirv_length

    def generate_vulkan_setup(self):
        template = open("litmus-setup-template.cpp", 'r')
        self.spirv_code()
        template_content = template.read()
        template.close()
        for key in self.template_replacements:
            template_content = template_content.replace("{{ " + key + " }}", str(self.template_replacements[key]))
        output_file = open(self.test_name + "-vulkan-setup.cpp", "w")
        output_file.write(template_content)
        output_file.close()

def main(argv):
    test_config_file_name = argv[1]
    parameter_config_file_name = argv[2]
    test_config_file = open(test_config_file_name, "r")
    parameter_config_file = open(parameter_config_file_name, "r")
    test_config = json.loads(test_config_file.read())
    parameter_config = json.loads(parameter_config_file.read())
    litmus_test = LitmusTest(test_config, parameter_config)
    litmus_test.generate()

if __name__ == '__main__':
    main(sys.argv)

