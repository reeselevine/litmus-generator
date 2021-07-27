import os

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
        use_rmw = False
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
                if 'useRMW' in instruction:
                    use_rmw = instruction['useRMW']
                if instruction['action'] == "read":
                    if instruction['variable'] not in self.variables:
                        self.variables[instruction['variable']] = variable_output
                        variable_output += 1
                    instructions.append(self.ReadInstruction(instruction['memoryLocation'], instruction['variable'], mem_order, use_rmw))
                if instruction['action'] == "write":
                    instructions.append(self.WriteInstruction(instruction['memoryLocation'], instruction['value'], mem_order, use_rmw))
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
        body_statements = []
        first_thread = True
        variable_init = []
        for variable, mem_loc in self.memory_locations.items():
            body_statements.append(self.generate_mem_loc(variable, mem_loc))
        for thread in self.threads:
            variables = set()
            thread_statements = self.generate_thread_header()
            for instr in thread.instructions:
                if isinstance(instr, self.ReadInstruction):
                    variables.add(instr.variable)
                thread_statements.append(self.backend_repr(instr))
            for variable in variables:
                thread_statements.append(self.results_repr(variable))
            thread_statements = ["    {}".format(statement) for statement in thread_statements]
            body_statements = body_statements + ["  {}".format(self.thread_filter(first_thread, thread.workgroup, thread.local_id))] + thread_statements
            first_thread = False
        body_statements = body_statements + ["  \n".join(self.generate_stress_call())]
        shader = "\n".join([self.generate_shader_def()] + body_statements + ["}\n"])
        meta_info = self.generate_meta()
        spin_func = self.generate_spin()
        stress_func = self.generate_stress()
        shader = "\n\n".join([meta_info, spin_func, stress_func, shader])
        filename = "target/" + self.test_name + self.file_ext()
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        with open(filename, "w") as output_file:
            output_file.write(shader)
    
    def file_ext(self):
        pass

    def generate_mem_loc(self, variable, mem_loc):
        pass

    def generate_thread_header(self):
        pass

    def backend_repr(self, instr):
        if isinstance(instr, self.ReadInstruction):
            return self.read_repr(instr)
        elif isinstance(instr, self.WriteInstruction):
            return self.write_repr(instr)
        elif isinstance(instr, self.MemoryFence):
            return self.fence_repr(instr)

    def read_repr(self, instr):
        pass

    def write_repr(self, instr):
        pass

    def fence_repr(self, instr):
        pass

    def results_repr(self, variable):
       pass 

    def thread_filter(self, first_thread, workgroup, thread):
        pass

    def generate_stress_call(self):
        pass

    def generate_shader_def(self):
        pass

    def generate_meta(self):
        pass

    def generate_stress(self):
        pass

    def generate_spin(self):
        pass

