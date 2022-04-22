import os
import json
import argparse

class LitmusTest:

    DEFAULT_MEM_ORDER = "relaxed"
    DEFAULT_TEST_TYPE = "inter_workgroup"
    DEFAULT_MEM_TYPE = "atomic_storage"

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

        def __init__(self, mem_order):
            self.mem_order = mem_order

    class Thread:
        def __init__(self, instructions):
            self.instructions = instructions

    def __init__(self, test_config):
        self.test_config = test_config
        self.threads = []
        self.behaviors = []
        self.read_threads = {}
        self.test_name = test_config['testName']
        if 'testType' in test_config:
          self.test_type = test_config['testType']
        else:
          self.test_type = self.DEFAULT_TEST_TYPE
        if 'memoryType' in test_config:
            self.memory_type = test_config['memoryType']
        else:
            self.memory_type = self.DEFAULT_MEM_TYPE
        self.initialize_threads()
        self.initialize_behaviors()

    # Code below this line initializes settings

    def initialize_threads(self):
        i = 0
        for thread in self.test_config['threads']:
            instructions = []
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
                if parsed_instr != None:
                    if not isinstance(parsed_instr, self.Fence):
                        if isinstance(parsed_instr, self.ReadInstruction) and parsed_instr.variable not in self.read_threads:
                            self.read_threads[parsed_instr.variable] = i
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
        test_code = []
        test_instrs = []
        i = 0
        for thread in self.threads:
            for instr in thread.instructions:
                test_instrs.append(self.backend_repr(instr, i))
            i += 1
        test_code += ["    " + "\n    ".join(test_instrs)]
        test_code += ["    " + "\n    ".join(self.generate_test_result_storage())]
        shader = self.build_test_shader("\n".join(test_code))
        filename = "target/" + self.test_name + self.file_ext()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as output_file:
            output_file.write(shader)

    def generate_test_result_storage(self):
        seen_ids = set()
        statements = []
        for behavior in self.behaviors:
            statements += self.generate_post_condition_stores(behavior.post_condition, seen_ids)
        return statements

    def generate_post_condition_stores(self, condition, seen_ids):
        result = []
        if isinstance(condition, self.PostConditionLeaf):
            if condition.identifier not in seen_ids:
                seen_ids.add(condition.identifier)
                if condition.output_type == "variable":
                    variable = condition.identifier
                    result.append(self.store_read_result_repr(variable, self.read_threads[variable]))
                elif condition.output_type == "memory" and "workgroup" in self.memory_type:
                    result.append(self.store_workgroup_mem_repr(condition.identifier))
        elif isinstance(condition, self.PostConditionNode):
            for cond in condition.conditions:
                result += self.generate_post_condition_stores(cond, seen_ids)
        return result


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

    def backend_repr(self, instr, i):
        if isinstance(instr, self.ReadInstruction):
            return self.read_repr(instr, i)
        elif isinstance(instr, self.WriteInstruction):
            return self.write_repr(instr, i)
        elif isinstance(instr, self.MemoryFence):
            return self.fence_repr(instr)

    def read_repr(self, instr, i):
        pass

    def write_repr(self, instr, i):
        pass

    def fence_repr(self, instr):
        pass

    def generate_result_shader_body(self):
        pass
