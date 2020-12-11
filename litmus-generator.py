import sys
import argparse
import json
import subprocess

mo_relaxed = "memory_order_relaxed"
mo_seq_cst = "memory_order_seq_cst"
DEFAULT_LOCAL_ID = 0

class LitmusTest:

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

    def __init__(self, config):
        self.config = config
        self.memory_locations = {}
        self.variables = {}
        self.threads = []
        self.post_conditions = []
        self.test_name = config['testName']
        self.template_replacements = {}
        self.initialize_threads(config)
        self.initialize_post_conditions(config)
        if 'numWorkgroups' in config:
            self.template_replacements['numWorkgroups'] = config['numWorkgroups']
        else:
            self.template_replacements['numWorkgroups'] = len(self.threads)

    def initialize_threads(self, config):
        mem_loc = 0
        variable_output = 0
        for thread in config['threads']:
            instructions = []
            for instruction in thread['actions']:
                if instruction['memoryLocation'] not in self.memory_locations:
                    self.memory_locations[instruction['memoryLocation']] = mem_loc
                    mem_loc += 1
                if instruction['action'] == "read":
                    if instruction['variable'] not in self.variables:
                        self.variables[instruction['variable']] = variable_output
                        variable_output += 1
                    instructions.append(self.ReadInstruction(self.memory_locations[instruction['memoryLocation']], instruction['variable']))
                if instruction['action'] == "write":
                    instructions.append(self.WriteInstruction(self.memory_locations[instruction['memoryLocation']], instruction['value']))
            if 'localId' in thread:
                local_id = thread['localId']
            else:
                local_id = DEFAULT_LOCAL_ID
            self.threads.append(self.Thread(thread['workgroup'], local_id, instructions))

    def generate(self):
        self.generate_openCL_kernel()
        self.generate_vulkan_setup()

    def generate_openCL_kernel(self):
        body_statements = []
        for thread in self.threads:
            spin = "spin(barrier);"
            variables = set()
            thread_statements = [spin]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements.append(instr.openCL_repr())
            for variable in variables:
                thread_statements.append("atomic_store_explicit(&results[{}], {}, {});".format(self.variables[variable], variable, mo_seq_cst))
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(thread.workgroup, thread.local_id))] + thread_statements + ["  }"]
        attribute = "__attribute__ ((reqd_work_group_size({}, 1, 1)))".format(self.template_replacements['numWorkgroups'])
        header = "__kernel void litmus_test(__global atomic_uint* test_data, __global atomic_uint* results, __global atomic_uint* barrier) {"
        kernel = "\n".join([attribute, header] + body_statements + ["}\n"])
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

    def thread_filter(self, workgroup, thread=0):
        return "if (get_group_id(0) == {} && get_local_id(0) == {}) {{".format(workgroup, thread)

    def initialize_post_conditions(self, config):
        num_outputs = 0
        for post_condition in config['postConditions']:
            if post_condition['type'] == "variable":
                num_outputs += 1
            self.post_conditions.append(self.PostCondition(post_condition['type'], post_condition['id'], post_condition['value']))
        self.template_replacements['numOutputs'] = num_outputs
        conditions = []
        for post_condition in self.post_conditions:
            if post_condition.output_type == "variable":
                conditions.append("output[{}] == {}".format(self.variables[post_condition.identifier], post_condition.value))
            elif post_condition.output_type == "memory":
                conditions.append("data[{}] == {}".format(self.memory_locations[post_condition.identifier], post_condition.value))
        self.template_replacements['postCondition'] = " && ".join(conditions)

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
    config_file_name = argv[1]
    config_file = open(config_file_name, "r")
    litmus_test_config = json.loads(config_file.read())
    litmus_test = LitmusTest(litmus_test_config)
    litmus_test.generate()

if __name__ == '__main__':
    main(sys.argv)

