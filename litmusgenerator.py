import json
import argparse
import wgsllitmustest
import vulkanlitmustest

def load_config(test_config):
    with open(test_config, "r") as test_config_file:
        test_config = json.loads(test_config_file.read())
        return test_config

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("test_config", help="Path to the test configuration")
    parser.add_argument("--backend", required=True, help="Backend to use. Valid options are opencl, vulkan, and wgsl")
    parser.add_argument("--gen_result_shader", action="store_true", help="If specified, also generates results aggregation shader for specified test.")
    args = parser.parse_args()
    test_config = load_config(args.test_config)
    if args.backend == "vulkan":
      test = vulkanlitmustest.VulkanLitmusTest(test_config)
    elif args.backend == "wgsl":
      test = wgsllitmustest.WgslLitmusTest(test_config)
    print("Generating {} litmus test for backend {}".format(test_config['testName'], args.backend))
    test.generate()
    if args.gen_result_shader:
      print("Generating {} litmus test result aggregation for backend {}".format(test_config['testName'], args.backend))
      test.generate_results_aggregator()

if __name__ == "__main__":
    main()