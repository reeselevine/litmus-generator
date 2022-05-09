import argparse
import json
import subprocess
import re
import csv
import os.path
import litmusenv
import litmustesttuner
import vulkanlitmusgenerator
import vulkanlitmussetup
import wgsllitmusgenerator

DEFAULT_TEST_PARAMETERS_FILE="litmus-config/test-parameters.json"
DEFAULT_CONFIG_DIR="litmus-config/"

env = litmusenv.LitmusEnv()

def generate_and_run(test_config, parameter_config, check_output):
    generate(test_config, parameter_config, "vulkan")
    output = run(test_config['testName'], check_output)
    return output

def generate(test_config, parameter_config, backend, result_agg=False):
    print("Generating {} litmus test for backend {}".format(test_config['testName'], backend))
    if backend == "vulkan":
        litmus_test = vulkanlitmusgenerator.VulkanLitmusTest(test_config)
        vulkan_setup = vulkanlitmussetup.VulkanLitmusSetup(litmus_test, parameter_config)
        litmus_test.generate()
        vulkan_setup.generate()
    elif backend == "wgsl":
        litmus_test = wgsllitmusgenerator.WgslLitmusTest(test_config)
        if result_agg:
            litmus_test.generate_results_aggregator()
        else:
            litmus_test.generate()

def run(test_name, check_output):
    subprocess.run([env.get("cppCompiler"), "-I{}".format(env.get("vulkanHeaders")), "-I{}".format(env.get("easyvkHeader")), "-std=gnu++14", "-o", "target/{}".format(test_name), "target/{}.cpp".format(test_name), "-leasyvk", "-lvulkan"])
    if check_output:
        output = subprocess.check_output(["./target/{}".format(test_name)])
        print(output.decode())
        return output.decode()
    else:
        subprocess.run(["./target/{}".format(test_name)])
        return None

def tune(test_config, parameter_config):
    print("Tuning {} litmus test".format(test_config['testName']))
    best_config = parameter_config.copy()
    most_weak_behaviors = get_results(generate_and_run(test_config, parameter_config, check_output = True))[0]
    for i in range(0, 10):
        litmustesttuner.randomize_config(parameter_config)
        weak_behaviors = get_results(generate_and_run(test_config, parameter_config, check_output = True))[0]
        if weak_behaviors > most_weak_behaviors:
            most_weak_behaviors = weak_behaviors
            best_config = parameter_config.copy()
    best_config['testName'] = test_config['testName']
    best_config['weakBehaviors'] = most_weak_behaviors
    print(json.dumps(best_config, indent=4))

def get_results(output):
    groups = re.search("weak behavior: (.*)\nnon weak behavior: (.*)\n", output)
    weak_behaviors = int(groups.group(1))
    non_weak_behaviors = int(groups.group(2))
    return (weak_behaviors, non_weak_behaviors)

def store_output(test_name, parameter_config, output, output_file_name):
    (weak_behaviors, non_weak_behaviors) = get_results(output)
    output_fields = parameter_config.copy()
    output_fields['testName'] = test_name
    output_fields['weakBehaviors'] = weak_behaviors
    output_fields['nonWeakBehaviors'] = non_weak_behaviors
    exists = os.path.exists(output_file_name)
    with open(output_file_name, "a") as output_file:
        writer = csv.DictWriter(output_file, fieldnames=list(output_fields.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(output_fields)

def load_config(args, test_file_name):
    with open(config_dir(args) + test_file_name + ".json", "r") as test_config_file:
        if args.paramsfile:
            parameter_config_file = open(args.paramsfile, "r")
        else:
            parameter_config_file = open(DEFAULT_TEST_PARAMETERS_FILE, "r")
        test_config = json.loads(test_config_file.read())
        parameter_config = json.loads(parameter_config_file.read())
        parameter_config_file.close()
        return (test_config, parameter_config)

def config_dir(args):
    if args.configdir:
        return args.configdir
    else:
        return DEFAULT_CONFIG_DIR

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("test_name", help="The name of the litmus test to run")
    parser.add_argument("--configdir", help="The config directory to search for the test configuration")
    parser.add_argument("--paramsfile", help="Parameters for stress and memory accesses")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-g", "--generate", action="store_true", help="Generate the litmus test kernel and setup code")
    group.add_argument("-gr", "--generate_and_run", action="store_true", help="Generate the litmus test and run it")
    group.add_argument("-grv", "--generate_and_run_variants", action="store_true", help="Generate variants of the litmus test and run them")
    parser.add_argument("--offset", help="When running a variant, which variant offset to start at")
    parser.add_argument("--outputfile", help="Output file to store results when running tests")
    parser.add_argument("--tune", action="store_true", help="Tune parameter config, should only be used when generating and running a test")
    parser.add_argument("--backend", help="Backend to use. Only valid when generating (not running) a litmus test. Valid options are vulkan and wgsl")
    parser.add_argument("--result_agg", action="store_true", help="Generate results aggregation shader for specified test")
    return parser.parse_args()

def main():
    args = parse_args()
    if args.outputfile == None:
        check_output = False
    else:
        check_output = True
    if args.generate:
        test_config, parameter_config = load_config(args, args.test_name)
        if args.backend:
            backend = args.backend
        else:
            backend = "vulkan"
        generate(test_config, parameter_config, backend, args.result_agg)
    elif args.generate_and_run:
        test_config, parameter_config = load_config(args, args.test_name)
        if args.tune:
            tune(test_config, parameter_config)
        else:
            output = generate_and_run(test_config, parameter_config, check_output)
            if output != None:
                store_output(test_config['testName'], parameter_config, output, args.outputfile)
    elif args.generate_and_run_variants:
        if args.offset:
            offset = args.offset
        else:
            offset = 0
        variant = args.test_name + "-variant-{}".format(offset)
        while os.path.exists(config_dir(args) + variant + ".json"):
            test_config, parameter_config = load_config(args, variant)
            generate(test_config, parameter_config)
            output = run(args.test_name, check_output)
            if output != None:
                store_output(variant, parameter_config, output, "results/" + args.outputfile)
            offset += 1
            variant = args.test_name + "-variant-{}".format(offset)


if __name__ == "__main__":
    main()
