import os
import json
import argparse

class LitmusTest:

    DEFAULT_MEM_ORDER = "relaxed"

    class Behavior:

        def __init__(self, key, post_condition):
            self.key = key
            self.post_condition = post_condition

    class PostCondition:
        pass

    class PostConditionNode:

        def __init__(self, operator, conditions):
            self.operator = operator
            self.conditions = conditions

    class PostConditionLeaf:

        def __init__(self, output_type, identifier, value):
            self.output_type = output_type
            self.identifier = identifier
            self.value = value

    class Instruction:
        pass

    class ReadInstruction(Instruction):

        def __init__(self, mem_loc, variable, mem_order, use_rmw):
            self.mem_loc = mem_loc
            self.variable = variable
            self.mem_order = mem_order
            self.use_rmw = use_rmw

    class WriteInstruction(Instruction):

        def __init__(self, mem_loc, value, mem_order, use_rmw):
            self.mem_loc = mem_loc
            self.value = value
            self.mem_order = mem_order
            self.use_rmw = use_rmw

    class Fence(Instruction):
        pass

    class MemoryFence(Fence):

        def __init__(self, mem_order):
            self.mem_order = mem_order

    class Barrier(Fence):

        def __init__(self):
            pass

    class Thread:
        def __init__(self, instructions):
            self.instructions = instructions

    def __init__(self, test_config):
        self.test_config = test_config
        self.threads = []
        self.behaviors = []
        self.variable_offsets = {}
        self.read_threads = {}
        self.test_name = test_config['testName']
        if 'sameWorkgroup' in test_config:
          self.same_workgroup = test_config['sameWorkgroup']
        else:
          self.same_workgroup = False
        if 'workgroupMemory' in test_config:
            self.workgroup_memory = test_config['workgroupMemory']
        else:
            self.workgroup_memory = False
        self.initialize_threads()
        self.initialize_behaviors()

    # Code below this line initializes settings

    def initialize_threads(self):
        i = 0
        for thread in self.test_config['threads']:
            instructions = []
            j = 0
            for instruction in thread['actions']:
                use_rmw = False
                if 'memoryOrder' in instruction:
                    mem_order = instruction['memoryOrder']
                else:
                    mem_order = self.DEFAULT_MEM_ORDER
                parsed_instr = None
                if 'useRMW' in instruction:
                    use_rmw = instruction['useRMW']
                if instruction['action'] == "read":
                    parsed_instr = self.ReadInstruction(instruction['memoryLocation'], instruction['variable'], mem_order, use_rmw)
                elif instruction['action'] == "write":
                    parsed_instr = self.WriteInstruction(instruction['memoryLocation'], instruction['value'], mem_order, use_rmw)
                elif instruction['action'] == "fence":
                    parsed_instr = self.MemoryFence(mem_order)
                elif instruction['action'] == "barrier":
                    parsed_instr = self.Barrier()
                if parsed_instr != None:
                    if not isinstance(parsed_instr, self.Fence):
                        if parsed_instr.mem_loc not in self.variable_offsets:
                            self.variable_offsets[parsed_instr.mem_loc] = j
                        if isinstance(parsed_instr, self.ReadInstruction) and parsed_instr.variable not in self.read_threads:
                            self.read_threads[parsed_instr.variable] = i
                        j += 1
                    instructions.append(parsed_instr)
            self.threads.append(self.Thread(instructions))
            i += 1

    def build_post_condition(self, condition):
        if condition['type'] == "op":
            children = []
            for cond in condition['conditions']:
                children.append(self.build_post_condition(cond))
            return self.PostConditionNode(condition['op'], children)
        else:
            return self.PostConditionLeaf(condition['type'], condition['id'], condition['value'])

    def initialize_behaviors(self):
        for behavior in self.test_config['behaviors']:
            self.behaviors.append(self.Behavior(behavior, self.build_post_condition(self.test_config['behaviors'][behavior])))

    def generate(self):
        body_statements = []
        test_mem_locs = []
        test_instrs = []
        i = 0
        results = []
        for thread in self.threads:
            j = 0
            for instr in thread.instructions:
                if not isinstance(instr, self.Fence):
                    test_mem_locs.append(self.generate_mem_loc(instr.mem_loc, i, self.variable_offsets[instr.mem_loc], self.same_workgroup and not self.workgroup_memory))
                    j += 1
                    if isinstance(instr, self.ReadInstruction):
                        results.append(self.results_repr(instr.variable, i))
                test_instrs.append(self.backend_repr(instr, i))
            i += 1
        body_statements += ["    " + "\n    ".join(self.generate_threads_header(test_mem_locs))]
        body_statements += ["    " + "\n    ".join(test_instrs)]
        body_statements += ["    " + "\n    ".join(self.generate_result_storage())]
        body_statements += ["\n".join(self.generate_stress_call())]
        shader = "\n".join([self.generate_shader_def()] + body_statements + ["}\n"])
        meta_info = self.generate_meta()
        spin_func = self.generate_spin()
        stress_func = self.generate_stress()
        shader = "\n\n".join([meta_info, spin_func, stress_func, shader])
        filename = "target/" + self.test_name + self.file_ext()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as output_file:
            output_file.write(shader)

    def generate_results_aggregator(self):
        result_meta_info = self.generate_result_meta()
        header = self.generate_result_shader_def()
        statements = ["  " + "\n  ".join(self.generate_result_shader_body())]
        statements.append("}\n")
        shader_fn = "\n".join([header] + statements)
        result_shader = "\n\n".join([result_meta_info, shader_fn])
        result_filename = "target/" + self.test_name + "-results" + self.file_ext()
        os.makedirs(os.path.dirname(result_filename), exist_ok=True)
        with open(result_filename, "w") as output_file:
            output_file.write(result_shader)



    def file_ext(self):
        pass

    def generate_mem_loc(self, variable, mem_loc):
        pass

    def generate_threads_header(self):
        pass

    def backend_repr(self, instr, i):
        if isinstance(instr, self.ReadInstruction):
            return self.read_repr(instr, i)
        elif isinstance(instr, self.WriteInstruction):
            return self.write_repr(instr, i)
        elif isinstance(instr, self.MemoryFence):
            return self.fence_repr(instr)
        elif isinstance(instr, self.Barrier):
            return self.barrier_repr(instr)

    def read_repr(self, instr, i):
        pass

    def write_repr(self, instr, i):
        pass

    def fence_repr(self, instr):
        pass

    def barrier_repr(self, instr):
        pass

    def results_repr(self, variable, i):
      pass

    def generate_stress_call(self):
        pass

    def generate_shader_def(self):
        pass

    def generate_result_shader_def(self):
        pass

    def generate_meta(self):
        pass

    def generate_result_meta(self):
        pass

    def generate_stress(self):
        pass

    def generate_spin(self):
        pass

    def generate_result_storage(self):
        pass

    def generate_result_shader_body(self):
        pass