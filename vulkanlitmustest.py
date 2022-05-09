import subprocess
import opencllitmustest

class VulkanLitmusTest(opencllitmustest.OpenCLLitmusTest):

    def gen_spirv(self, filename):
        subprocess.run(["clspv", "--cl-std=CL2.0", "--inline-entry-points", "target/" + filename + ".cl", "-o",  "target/" + filename + ".spv"])

    def generate(self):
        super()
        self.gen_spirv(self.test_name)

    def generate_results_aggregator(self):
        super()
        self.gen_spirv(self.test_name + "-results")
