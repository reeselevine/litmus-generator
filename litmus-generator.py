import sys
import argparse

mo_relaxed = "memory_order_relaxed"
mo_seq_cst = "memory_order_seq_cst"

def generate_spin():
    header = "void spin(__global atomic_uint* barrier) {"
    body = "\n  ".join([
        header,
        "int i = 0;",
        "atomic_fetch_add_explicit(barrier, 1, memory_order_relaxed);",
        "while (i < 1000 & val < 2) {",
        "  val = {}".format(generate_atomic_load("barrier", mo_relaxed)),
        "  i++;",
        "}"
    ])
    return "\n".join([body, "}"])

def generate_atomic_load(var, mem_order):
    return "atomic_load_explicit({}, {});".format(var, mem_order)

def generate_atomic_store(loc, value, mem_order):
    return "atomic_store_explicit({}, {}, {});".format(loc, value, mem_order)

def thread_filter(workgroup, thread=0):
    return "if (get_group_id(0) == {} && get_local_id(0) == {}) {{".format(workgroup, thread)

def generate_kernel(test):
    attribute = "__attribute__ ((reqd_work_group_size(2, 1, 1)))"
    header = "__kernel void litmus_test(__global atomic_uint* test_data, __global atomic_uint* results) {"
    spin = "spin(&test_data[2]);"
    store_x = generate_atomic_store("&test_data[0]", 1, mo_relaxed)
    store_y = generate_atomic_store("&test_data[1]", 1, mo_relaxed)
    load_x = "uint tmpx = {}".format(generate_atomic_load("&test_data[0]", mo_relaxed))
    load_y = "uint tmpy = {}".format(generate_atomic_load("&test_data[1]", mo_relaxed))
    output_x = generate_atomic_store("&results[0]", "tmpx", mo_seq_cst)
    output_y = generate_atomic_store("&results[1]", "tmpy", mo_seq_cst)
    thread1_statements = []
    thread2_statements = []
    if test == "SB":
        thread1_statements = [store_x, load_y, output_y]
        thread2_statements = [store_y, load_x, output_x]
    elif test == "LB":
        thread1_statements = [load_y, store_x, output_y]
        thraed2_statements = [load_x, store_y, output_x]
    elif test == "MP":
        thread1_statements = [store_y, store_x]
        thread2_statements = [load_x, load_y, output_x, output_y]
    thread1_statements = [spin] + thread1_statements
    thread2_statements = [spin] + thread2_statements
    thread1_statements = ["    {}".format(statement) for statement in thread1_statements]
    thread2_statements = ["    {}".format(statement) for statement in thread2_statements]
    thread1_statements = ["  {}".format(thread_filter(0))] + thread1_statements + ["  }"]
    thread2_statements = ["  {}".format(thread_filter(1))] + thread2_statements + ["  }"]
    return "\n".join([attribute, header] + thread1_statements + thread2_statements + ["}\n"])


def generate_program(test):
    spin_func = generate_spin()
    kernel = generate_kernel(test)
    return "\n\n".join([spin_func, kernel])

def main(argv):
    litmus_test = argv[1]
    output_file = argv[2]
    generated_test = generate_program(litmus_test)
    f = open(output_file, "w")
    f.write(generated_test)
    f.close()

if __name__ == '__main__':
    main(sys.argv)

