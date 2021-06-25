import argparse
import json
import subprocess
import litmusgenerator
import re
import csv
import os.path

DEFAULT_TEST_PARAMETERS_FILE="litmus-config/test-parameters.json"
DEFAULT_CONFIG_DIR="litmus-config/"

def generate(test_config, parameter_config):
    print("Generating {} litmus test".format(test_config['testName']))
    litmus_test = litmusgenerator.LitmusTest(test_config, parameter_config)
    litmus_test.generate()

def run(test_name, check_output):
    subprocess.run(["/usr/bin/c++", "-I/shared/vuh-sources/include", "-I/shared/easyvk/include", "-std=gnu++14", "-o", "exec", "{}.cpp".format(test_name), "-leasyvk", "-lvulkan"])
    if check_output:
        output = subprocess.check_output(["./exec"])
        print(output.decode())
        return output.decode()
    else:
        subprocess.run(["./exec"])
        return None

def tune(test_config, parameter_config):
     print("Tuning {} litmus test".format(test_config['testName']))

def store_output(test_name, parameter_config, output, output_file_name):
    groups = re.search("weak behavior: (.*)\nnon weak behavior: (.*)\n", output)
    weak_behaviors = int(groups.group(1))
    non_weak_behaviors = int(groups.group(2))
    output_fields = parameter_config.copy()
    output_fields['testName'] = test_name
    output_fields['weakBehaviors'] = weak_behaviors
    output_fields['nonWeakBehaviors'] = non_weak_behaviors
    exists = os.path.exists(output_file_name)
    output_file = open(output_file_name, "a")
    writer = csv.DictWriter(output_file, fieldnames=list(output_fields.keys()))
    if not exists:
        writer.writeheader()
    writer.writerow(output_fields)
    output_file.close()

def load_config(args, test_file_name):
    test_config_file = open(config_dir(args) + test_file_name + ".json", "r")
    if args.paramsfile:
        parameter_config_file = open(args.paramsfile, "r")
    else:
        parameter_config_file = open(DEFAULT_TEST_PARAMETERS_FILE, "r")
    test_config = json.loads(test_config_file.read())
    parameter_config = json.loads(parameter_config_file.read())
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
    return parser.parse_args()

def main():
    args = parse_args()
    if args.outputfile == None:
        check_output = False
    else:
        check_output = True
    if args.generate:
        test_config, parameter_config = load_config(args, args.test_name)
        generate(test_config, parameter_config)
    elif args.generate_and_run:
        test_config, parameter_config = load_config(args, args.test_name)
        if args.tune:
            tune(test_config, parameter_config)
        else:
            generate(test_config, parameter_config)
            output = run(test_config['testName'], check_output)
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
                store_output(variant, parameter_config, output, args.outputfile)
            offset += 1
            variant = args.test_name + "-variant-{}".format(offset)


if __name__ == "__main__":
    main()
