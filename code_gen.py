def write_headers(headers):
    return "\n".join(headers)

def write_declaration(name, _type, opt_array=''):
    return "{} {}{}".format(_type, name, opt_array)

def write_fn_signature(fn_name, ret_type, arg_list):
    def write_arg(arg_tuple):
        if len(arg_tuple) == 2:
            return write_declaration(arg_tuple[0], arg_tuple[1])
        elif len(arg_tuple) == 3:
            return write_declaration(arg_tuple[0], arg_tuple[1], arg_tuple[2])
    args = list(map(write_arg, arg_list))
    fn_type_name = write_declaration(fn_name, ret_type)
    return "{}({})".format(fn_type_name, ", ".join(args))

def write_fn(signature, body):
    return "{} {{\n{}\n}}".format(signature, "  ".join(('\n' + body).splitlines()))

def write_call_fn(fn_name, args):
    return "{}({});".format(fn_name, ", ".join(args))

def write_hello_world():
    signature = write_fn_signature("main", "int", [("argc", "int"), ("argv", "char*", "[]")])
    body = write_call_fn("printf", ['"hello %s, you are %d years old.\\n"', '"Reese"', "25"])
    function = write_fn(signature, body)
    headers = write_headers(["#include <stdio.h>"])
    return "{}\n\n{}".format(headers, function)

if __name__ == "__main__":
    print(write_hello_world())
