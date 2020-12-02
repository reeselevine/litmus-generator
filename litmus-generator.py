import sys
import argparse
import json

mo_relaxed = "memory_order_relaxed"
mo_seq_cst = "memory_order_seq_cst"

class LitmusTest:

    def __init__(self, config):
        self.config = config
        self.memory_locations = {}
        self.variables = {}
        self.threads = []
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
                    instructions += [self.ReadInstruction(self.memory_locations[instruction['memoryLocation']], instruction['variable'])]
                if instruction['action'] == "write":
                    instructions += [self.WriteInstruction(self.memory_locations[instruction['memoryLocation']], instruction['value'])]
            self.threads += [self.Thread(thread['workgroup'], instructions)]

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
        def __init__(self, workgroup, instructions):
            self.workgroup = workgroup
            self.instructions = instructions

    def generate_openCL_kernel(self):
        body_statements = []
        for thread in self.threads:
            spin = "spin(barrier);"
            variables = set()
            thread_statements = [spin]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements += [instr.openCL_repr()]
            for variable in variables:
                thread_statements += ["atomic_store_explicit(&results[{}], {}, {});".format(self.variables[variable], variable, mo_seq_cst)]
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(thread.workgroup))] + thread_statements + ["  }"]
        attribute = "__attribute__ ((reqd_work_group_size({}, 1, 1)))".format(len(self.threads))
        header = "__kernel void litmus_test(__global atomic_uint* test_data, __global atomic_uint* results, __global atomic_uint* barrier) {"
        kernel = "\n".join([attribute, header] + body_statements + ["}\n"])
        spin_func = self.generate_spin()
        return "\n\n".join([spin_func, kernel])

    def generate_spin(self):
        header = "static void spin(__global atomic_uint* barrier) {"
        body = "\n  ".join([
            header,
            "int i = 0;",
            "uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
            "while (i < 1000 && val < 2) {",
            "  val = atomic_load_explicit(barrier, memory_order_relaxed);",
            "  i++;",
            "}"
        ])
        return "\n".join([body, "}"])

    def thread_filter(self, workgroup, thread=0):
        return "if (get_group_id(0) == {} && get_local_id(0) == {}) {{".format(workgroup, thread)

def main(argv):
    config_file_name = argv[1]
    output_file = argv[2]
    config_file = open(config_file_name, "r")
    litmus_test_config = json.loads(config_file.read())
    litmus_test = LitmusTest(litmus_test_config)
    generated_test = litmus_test.generate_openCL_kernel()
    f = open(output_file, "w")
    f.write(generated_test)
    f.close()

if __name__ == '__main__':
    main(sys.argv)

