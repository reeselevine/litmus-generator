import argparse

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("test_name", help="The name of the litmus test to run")
    parser.add_argument("--test_parameters", help="Parameters for stress and memory accesses")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-g", "--generate", action="store_true", help="Generate the litmus test kernel and setup code")
    group.add_argument("-gr", "--generate-and-run", action="store_true", help="Generate the litmus test and run it")
    group.add_argument("-grv", "--generate-and-run-variants", action="store_true", help="Generate variants of the litmus test and run them")
    parser.add_argument("--offset", help="When running a variant, which variant offset to start at")
    args = parser.parse_args()
    print(args.test_name)


if __name__ == "__main__":
    main()
