import json
import sys

def build_cache_repr(config):
    cache_repr = ""
    for thread in config['threads']:
        for instruction in thread['actions']:
            cache_repr += instruction['action'] + "-"
            if 'memoryOrder' in instruction:
                cache_repr += instruction['memoryOrder']
            else:
                cache_repr += 'relaxed'
            cache_repr += "-"
    return cache_repr[:-1]

def generate_weaker_variants(config, variant, cache):
    cache_repr = build_cache_repr(config)
    if cache_repr in cache:
        return variant
    cache.add(cache_repr)
    cur_variant = variant
    for thread in config['threads']:
        for instruction in thread['actions']:
            if 'memoryOrder' in instruction and instruction['memoryOrder'] != "relaxed":
                if instruction['memoryOrder'] == "sc":
                    if instruction['action'] == "write":
                        instruction['memoryOrder'] = "release"
                    else:
                        instruction['memoryOrder'] = "acquire"
                    cur_variant = generate_weaker_variants(config, cur_variant, cache)
                    instruction['memoryOrder'] = "sc"
                elif instruction['memoryOrder'] == "acquire":
                    instruction['memoryOrder'] = "relaxed"
                    cur_variant = generate_weaker_variants(config, cur_variant, cache)
                    instruction['memoryOrder'] = "acquire"
                elif instruction['memoryOrder'] == "release":
                    instruction['memoryOrder'] = "relaxed"
                    cur_variant = generate_weaker_variants(config, cur_variant, cache)
                    instruction['memoryOrder'] = "release"
    litmus_variant_name = config['testName'] + "-variant-" + str(cur_variant) + ".json"
    litmus_variant_file = open("litmus-config/" + config['testName'] + "-variants/" + litmus_variant_name, "w")
    litmus_variant_file.write(json.dumps(config, indent=4))
    litmus_variant_file.close()
    return cur_variant + 1


def main(argv):
    test_config_file_name = argv[1]
    test_config_file = open("litmus-config/minimally-forbidden-variants/" + test_config_file_name + ".json", "r")
    test_config = json.loads(test_config_file.read())
    generate_weaker_variants(test_config, 0, set())

if __name__ == '__main__':
    main(sys.argv)

