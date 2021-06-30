class LitmusTest:

    DEFAULT_LOCAL_ID = 0
    DEFAULT_MEM_ORDER = "relaxed"

    class PostCondition:

        def __init__(self, output_type, identifier, value):
            self.output_type = output_type
            self.identifier = identifier
            self.value = value

    class Instruction:
        pass

    class ReadInstruction(Instruction):

        def __init__(self, mem_loc, variable, mem_order):
            self.mem_loc = mem_loc
            self.variable = variable
            self.mem_order = mem_order

    class WriteInstruction(Instruction):

        def __init__(self, mem_loc, value, mem_order):
            self.mem_loc = mem_loc
            self.value = value
            self.mem_order = mem_order

    class MemoryFence(Instruction):

        def __init__(self, mem_order):
            self.mem_order = mem_order

    class Thread:
        def __init__(self, workgroup, local_id, instructions):
            self.workgroup = workgroup
            self.local_id = local_id
            self.instructions = instructions

    def __init__(self, test_config):
        self.test_config = test_config
        self.memory_locations = {}
        self.variables = {}
        self.threads = []
        self.post_conditions = []
        self.test_name = test_config['testName']
        self.initialize_threads()
        self.initialize_post_conditions()

    # Code below this line initializes settings

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

    def generate(self):
        pass
