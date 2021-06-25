# Litmus Test Generator for the Vulkan Framework

Vulkan is a modern API for GPU programming, allowing code to be written once and run across a variety of operating systems and hardware devices. Litmus tests are short concurrent programs that reveal relaxed behaviors in weak memory models and can be used to empirically test those models. Modern GPUs and the Vulkan API expose a weak memory model, but exploration and an understanding of the real world behaviors of this model are still being developed. This tool provides a way to specify litmus tests and associated stress parameters and run the tests using the Vulkan API.

## Dependencies

This tool depends on [clspv](https://github.com/google/clspv) for compiling OpenCL to SPIR-V and [easyvk](https://github.com/reeselevine/easyvk) and [vulkan-headers](https://github.com/KhronosGroup/Vulkan-Headers) for working with the Vulkan API. Install locations for the header files should be specified in `litmus-config/env.json`, and the installed binaries should be added to the `LD_LIBRARY_PATH`.

## Lifecycle of a test
A litmus test starts out as a json configuration file which defines the set of actions each thread takes and an associated post-condition. While this post-condition can examine any memory or variable value in the test, it most commonly defines the relaxed behavior possible by this test. The library of litmus tests is stored in the `litmus-config` directory.

A litmus test is run along with a corresponding set of test parameters which may make it more likely for a relaxed behavior to show up. These parameters are also stored in json in the `test-parameters` file.

To run a litmus test, a python script takes as input the configuration, generates several artifacts, and optionally runs the test. The artifacts are placed in the `target/` directory and are as follows:

`<test-name>.cpp`: This is the C++ file that when compiled, will run the test.

`<test-name>.cl`: OpenCL representation of the litmus test. While OpenCL is easy to program in, Vulkan requires SPIR-V to run.

`<test-name>.spv`: SPIR-V representation of the litmus test. This is generated from the OpenCL code using CLSPV.

## Running a test

The python script that generates and optionally runs the test is called `litmustestrunner.py`. Running `python3 litmustestrunner.py -h` will give documentation of all the available options, but here are some frequently used commands:

`python3 litmustestrunner.py <test-name> -g`: This will generate the files above for the test, and the c++ file must then be manually compiled and run. A helper script, `compile.sh`, can be used for this purpose. By default, the script looks in the `litmus-config` directory for the litmus test and test parameters configuration.

`python3 litmustestrunner.py <test-name> -gr`: This will both generate the files and run the test, outputting the results to STDOUT. 

`python3 litmustestrunner.py <test-name> -gr --outputfile example.csv`: This will generate and run the test, storing the number of relaxed behaviors along with the test configuration in a csv file. This is useful when running different configurations in order to find settings that reveal more relaxed behaviors.
