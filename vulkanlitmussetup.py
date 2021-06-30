import subprocess
import litmusenv

class VulkanLitmusSetup:

    defaults_dict = {
        "minWorkgroups": 4,
        "maxWorkgroups": 4,
        "minWorkgroupSize": 1,
        "maxWorkgroupSize": 1,
        "shufflePct": 0,
        "barrierPct": 0,
        "memStride": 1,
        "memStressPct": 0,
        "memStressIterations": 100,
        "stressLineSize": 2,
        "stressTargetLines": 1,
        "stressAssignmentStrategy": "ROUND_ROBIN",
        "preStressPct": 0,
        "preStressIterations": 100,
        "testIterations": 10000,
        "gpuDeviceId": -1
    }

    stress_dict = {
        "storestore": 0,
        "storeload": 1,
        "loadstore": 2,
        "loadload": 3
    }

    def __init__(self, litmus_test, parameter_config):
        self.env = litmusenv.LitmusEnv()
        self.litmus_test = litmus_test
        self.parameter_config = parameter_config
        self.template_replacements = {}
        self.template_replacements['testName'] = self.litmus_test.test_name
        self.initialize_template_replacements()

    def initialize_stress_settings(self):

        def init_stress_pattern(key):
            if key in self.parameter_config:
                self.template_replacements[key] = self.stress_dict["".join(self.parameter_config[key])]
            else:
                self.template_replacements[key] = 0

        min_size = self.template_replacements['stressLineSize'] * self.template_replacements['stressTargetLines']
        if 'scratchMemorySize' in self.parameter_config:
            if self.parameter_config['scratchMemorySize'] < min_size:
                raise Exception("scratch memory too small")
            else:
                self.template_replacements['scratchMemorySize'] = self.parameter_config['scratchMemorySize']
        else:
            self.template_replacements['scratchMemorySize'] = min_size
        init_stress_pattern("memStressPattern")
        init_stress_pattern("preStressPattern")

    def initialize_memory_size(self):
        min_test_memory_size = self.template_replacements['memStride'] * len(self.litmus_test.memory_locations)
        if 'testMemorySize' in self.parameter_config:
            if self.parameter_config['testMemorySize'] < min_test_memory_size:
                raise Exception("test memory too small")
            else:
                self.template_replacements['testMemorySize'] = self.parameter_config['testMemorySize']
        else:
            self.template_replacements['testMemorySize'] = min_test_memory_size
        self.template_replacements['numMemLocations'] = len(self.litmus_test.memory_locations)

    def initialize_post_conditions(self):
        num_outputs = 0
        for post_condition in self.litmus_test.post_conditions:
            if post_condition.output_type == "variable":
                num_outputs += 1
        self.template_replacements['numOutputs'] = max(num_outputs, 1)
        conditions = []
        sample_ids = []
        sample_values = []
        weak_values = []
        for post_condition in self.litmus_test.post_conditions:
            sample_ids.append("{}: %u".format(post_condition.identifier))
            weak_values.append("{}: {}".format(post_condition.identifier, post_condition.value))
            if post_condition.output_type == "variable":
                sample_values.append("results.load({})".format(self.litmus_test.variables[post_condition.identifier]))
                conditions.append("results.load({}) == {}".format(self.litmus_test.variables[post_condition.identifier], post_condition.value))
            elif post_condition.output_type == "memory":
                sample_values.append("testData.load(memLocations.load({}))".format(self.memory_locations[post_condition.identifier]))
                conditions.append("testData.load(memLocations.load({})) == {}".format(self.memory_locations[post_condition.identifier], post_condition.value))
        self.template_replacements['weakBehaviorStr'] = ", ".join(weak_values)
        self.template_replacements['postConditionSample'] = """printf("{}\\n", {});""".format(", ".join(sample_ids), ",".join(sample_values))
        self.template_replacements['postCondition'] = " && ".join(conditions)

    def initialize_template_replacements(self):
        for key in self.defaults_dict:
            if key in self.parameter_config:
                self.template_replacements[key] = self.parameter_config[key]
            else:
                self.template_replacements[key] = self.defaults_dict[key]
        self.initialize_memory_size()
        self.initialize_stress_settings()
        self.initialize_post_conditions()

    def spirv_code(self):
        print("Generating SPIRV code")
        subprocess.run([self.env.get("clspv"), "--cl-std=CL2.0", "--inline-entry-points", "target/" + self.litmus_test.test_name + ".cl", "-o",  "target/" + self.litmus_test.test_name + ".spv"])

    def generate(self):
        print("Building vulkan setup code")
        with open("litmus-config/litmus-template.cpp", 'r') as template:
            self.spirv_code()
            template_content = template.read()
        for key in self.template_replacements:
            template_content = template_content.replace("{{ " + key + " }}", str(self.template_replacements[key]))
        with open("target/" + self.litmus_test.test_name + ".cpp", "w") as output_file:
            output_file.write(template_content)
