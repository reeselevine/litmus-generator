import sys
import argparse

mo_relaxed = "memory_order_relaxed"
mo_seq_cst = "memory_order_seq_cst"

class InputError(Exception):

    def __init__(self, message):
        self.message = message

class LitmusTest:

    def __init__(self, thread_dict):
        self.memory_locations = {}
        self.registers = {}
        self.threads = []
        mem_loc = 0
        register_output = 0
        for thread, instrs in thread_dict.items():
            instructions = []
            for instruction in instrs:
                if instruction[1] not in self.memory_locations:
                    self.memory_locations[instruction[1]] = mem_loc
                    mem_loc += 1
                if instruction[0] == "r":
                    if instruction[2] not in self.registers:
                        self.registers[instruction[2]] = register_output
                        register_output += 1
                    instructions += [self.ReadInstruction(self.memory_locations[instruction[1]], instruction[2])]
                if instruction[0] == "w":
                    instructions += [self.WriteInstruction(self.memory_locations[instruction[1]], instruction[2])]
            self.threads += [self.Thread(instructions)]

    class Instruction:

        def openCl_repr(self):
            pass

    class ReadInstruction(Instruction):

        def __init__(self, mem_loc, register):
            self.mem_loc = mem_loc
            self.register = register

        def openCL_repr(self):
            return "uint {} = atomic_load_explicit(&test_data[{}], {});".format(self.register, self.mem_loc, mo_relaxed)

    class WriteInstruction(Instruction):

        def __init__(self, mem_loc, value):
            self.mem_loc = mem_loc
            self.value = value

        def openCL_repr(self):
            return "atomic_store_explicit(&test_data[{}], {}, {});".format(self.mem_loc, self.value, mo_relaxed)

    class Thread:
        def __init__(self, instructions):
            self.instructions = instructions

    def generate_openCL_kernel(self):
        body_statements = []
        for i in range(0, len(self.threads)):
            thread = self.threads[i]
            spin = "spin(&test_data[2]);"
            registers = set()
            thread_statements = [spin]
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    registers.add(instr.register)
                thread_statements += [instr.openCL_repr()]
            for register in registers:
                thread_statements += ["atomic_store_explicit(&results[{}], {}, {});".format(self.registers[register], register, mo_seq_cst)]
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(thread_filter(i))] + thread_statements + ["  }"]
        attribute = "__attribute__ ((reqd_work_group_size({}, 1, 1)))".format(len(self.threads))
        header = "__kernel void litmus_test(__global atomic_uint* test_data, __global atomic_uint* results) {"
        return "\n".join([attribute, header] + body_statements + ["}\n"])

def generate_spin():
    header = "static void spin(__global atomic_uint* barrier) {"
    body = "\n  ".join([
        header,
        "int i = 0;",
        "uint val = atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
        "while (i < 1000 && val < 2) {",
        "  val = {}".format(generate_atomic_load("barrier", mo_relaxed)),
        "  i++;",
        "}"
    ])
    return "\n".join([body, "}"])

def thread_filter(workgroup, thread=0):
    return "if (get_group_id(0) == {} && get_local_id(0) == {}) {{".format(workgroup, thread)

def generate_program(test):
    thread_dict = {}
    if test == "SB":
        thread_dict[0] = [("w", "x", 1), ("r", "y", "r0")]
        thread_dict[1] = [("w", "y", 1), ("r", "x", "r1")]
    elif test == "LB":
        thread_dict[0] = [("r", "y", "r0"), ("w", "x", 1)]
        thread_dict[1] = [("r", "x", "r1"), ("w", "y", 1)]
    elif test == "MP":
        thread_dict[0] = [("w", "y", 1), ("w", "x", 1)]
        thread_dict[1] = [("r", "x", "r0"), ("r", "y", "r1")]
    litmus_test = LitmusTest(thread_dict)
    spin_func = generate_spin()
    kernel = litmus_test.generate_openCL_kernel()
    return "\n\n".join([spin_func, kernel])

def main(argv):
    litmus_test = argv[1]
    output_file = argv[2]
    generated_test = generate_program(litmus_test)
    f = open(output_file, "w")
    f.write(generated_test)
    f.close()

if __name__ == '__main__':
    main(sys.argv)

