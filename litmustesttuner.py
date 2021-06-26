import random

def randomize_config(config):
    config['barrierPct'] = random_pct()
    config['shufflePct'] = random_pct()
    config['memStressPct'] = random_pct()
    config['preStressPct'] = random_pct()
    config['stressLineSize'] = random_pow_2(10)
    config['memStride'] = random_pow_2(9)
    config['stressTargetLines'] = random.randint(1, 16)
    config["stressAssignmentStrategy"] = assignment_strategy()

    # Need to make sure there's enough memory for our stress
    config['scratchMemorySize'] = 4*config['stressLineSize'] * config['stressTargetLines']

def random_pct():
    return random.randint(0, 100)

def random_pow_2(max_pow):
    return pow(2, random.randint(1, max_pow))

def assignment_strategy():
    choices = ["ROUND_ROBIN", "CHUNKING"]
    return random.choice(choices)

