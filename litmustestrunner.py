import argparse
import json
import subprocess
import litmusgenerator
import re

DEFAULT_TEST_PARAMETERS_FILE="litmus-config/test-parameters.json"

def generate(test_config, parameter_config):
    litmus_test = litmusgenerator.LitmusTest(test_config, parameter_config)
    litmus_test.generate()

def run(test_name):
    subprocess.run(["/usr/bin/c++", "-I/shared/vuh-sources/include", "-std=gnu++14", "-o", "exec", "{}.cpp".format(test_name), "-lvuh", "-lvulkan"])
    output = subprocess.check_output(["./exec"])
    print(output.decode())
    return output.decode()

def store_output(test_config, output):
    groups = re.search("weak behavior: (.*)\nnon weak behavior: (.*)\n", output)
    weak_behaviors = int(groups.group(1))
    non_weak_behaviors = int(groups.group(2))

def load_config(args):
    test_config_file = open(args.test_name, "r")
    if args.test_parameters:
        parameter_config_file = open(parameter_config_file_name, "r")
    else:
        parameter_config_file = open(DEFAULT_TEST_PARAMETERS_FILE, "r")
    test_config = json.loads(test_config_file.read())
    parameter_config = json.loads(parameter_config_file.read())
    return (test_config, parameter_config)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("test_name", help="The name of the litmus test to run")
    parser.add_argument("--test_parameters", help="Parameters for stress and memory accesses")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-g", "--generate", action="store_true", help="Generate the litmus test kernel and setup code")
    group.add_argument("-gr", "--generate_and_run", action="store_true", help="Generate the litmus test and run it")
    group.add_argument("-grv", "--generate-and-run-variants", action="store_true", help="Generate variants of the litmus test and run them")
    parser.add_argument("--offset", help="When running a variant, which variant offset to start at")
    return parser.parse_args()


def main():
    args = parse_args()
    test_config, parameter_config = load_config(args)
    if args.generate:
        generate(test_config, parameter_config)
    elif args.generate_and_run:
        generate(test_config, parameter_config)
        output = run(test_config['testName'])
        store_output(test_config, output)


if __name__ == "__main__":
    main()
