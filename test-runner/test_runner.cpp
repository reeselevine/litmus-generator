#include <map>
#include <set>
#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
#include <chrono>
#include <easyvk.h>

using namespace std;
using namespace easyvk;

const int size = 4;

Device getDevice(Instance &instance, map<string, int> params) {
  int idx = 0;
  if (params.find("gpuDeviceId") != params.end()) {
    int j = 0;
    for (Device _device : instance.devices()) {
      if (_device.properties().deviceID == params["gpuDeviceId"]) {
        idx = j;
	break;
      }
      j++;
    }
  }
  Device device = instance.devices().at(idx);
  cout << "Using device " << device.properties().deviceName << "\n";
  return device;
}

void clearMemory(Buffer &gpuMem, int size) {
  for (int i = 0; i < size; i++) {
    gpuMem.store(i, 0);
  }
}

bool percentageCheck(int percentage) {
  return rand() % 100 < percentage;
}

void setShuffledWorkgroups(Buffer &shuffledWorkgroups, int numWorkgroups, int shufflePct) {
  for (int i = 0; i < numWorkgroups; i++) {
    shuffledWorkgroups.store(i, i);
  }
  if (percentageCheck(shufflePct)) {
    for (int i = numWorkgroups - 1; i > 0; i--) {
      int swap = rand() % (i + 1);
      int temp = shuffledWorkgroups.load(i);
      shuffledWorkgroups.store(i, shuffledWorkgroups.load(swap));
      shuffledWorkgroups.store(swap, temp);
    }
  }
}

/** Sets the stress regions and the location in each region to be stressed. Uses the stress assignment strategy to assign
  * workgroups to specific stress locations.
  */
void setScratchLocations(Buffer &locations, int numWorkgroups, map<string, int> params) {
  set <int> usedRegions;
  int numRegions = params["scratchMemorySize"] / params["stressLineSize"];
  for (int i = 0; i < params["stressTargetLines"]; i++) {
    int region = rand() % numRegions;
    while(usedRegions.count(region))
      region = rand() % numRegions;
    int locInRegion = rand() % (params["stressLineSize"]);
    switch (params["stressAssignmentStrategy"]) {
      case 0:
        for (int j = i; j < numWorkgroups; j += params["stressTargetLines"]) {
          locations.store(j, (region * params["stressLineSize"]) + locInRegion);
        }
        break;
      case 1:
        int workgroupsPerLocation = numWorkgroups/params["stressTargetLines"];
        for (int j = 0; j < workgroupsPerLocation; j++) {
          locations.store(i*workgroupsPerLocation + j, (region * params["stressLineSize"]) + locInRegion);
        }
        if (i == params["stressTargetLines"] - 1 && numWorkgroups % params["stressTargetLines"] != 0) {
          for (int j = 0; j < numWorkgroups % params["stressTargetLines"]; j++) {
            locations.store(numWorkgroups - j - 1, (region * params["stressLineSize"]) + locInRegion);
          }
        }
        break;
    }
  }
}

void setDynamicStressParams(Buffer &stressParams, map<string, int> params) {
  if (percentageCheck(params["barrierPct"])) {
    stressParams.store(0, 1);
  } else {
    stressParams.store(0, 0);
  }  
  if (percentageCheck(params["memStressPct"])) {
    stressParams.store(1, 1);
  } else {
    stressParams.store(1, 0);
  }  
  if (percentageCheck(params["preStressPct"])) {
    stressParams.store(4, 1);
  } else {
    stressParams.store(4, 0);
  }
}

void setStaticStressParams(Buffer &stressParams, map<string, int> params) {
  stressParams.store(2, params["memStressIterations"]);
  stressParams.store(3, params["memStressPattern"]);
  stressParams.store(5, params["preStressIterations"]);
  stressParams.store(6, params["preStressPattern"]);
  stressParams.store(7, params["permuteFirst"]);
  stressParams.store(8, params["permuteSecond"]);
  stressParams.store(9, params["testingWorkgroups"]);
  stressParams.store(10, params["memStride"]);
  if (params["aliasedMemory"] == 1) {
    stressParams.store(11, 0);
  } else {
    stressParams.store(11, params["memStride"]);
  }
}

int setWorkgroupSize(map<string, int> params)
{
  if (params["minWorkgroupSize"] == params["maxWorkgroupSize"])
  {
    return params["minWorkgroupSize"];
  }
  else
  {
    int size = rand() % (params["maxWorkgroupSize"] - params["minWorkgroupSize"]);
    return params["minWorkgroupSize"] + size;
  }
}

int setNumWorkgroups(map<string, int> params)
{
  if (params["testingWorkgroups"] == params["maxWorkgroups"])
  {
    return params["testingWorkgroups"];
  }
  else
  {
    int size = rand() % (params["maxWorkgroups"] - params["testingWorkgroups"]);
    return params["testingWorkgroups"] + size;
  }
}

void run(string &shader_file, map<string, int> params)
{
  // initialize settings
  auto instance = Instance(false);
  auto device = getDevice(instance, params);
  int workgroupSize = setWorkgroupSize(params);
  int testingThreads = workgroupSize * params["testingWorkgroups"];
  int testLocSize = testingThreads * params["numMemLocations"] * params["memStride"];

  // set up buffers
  auto testLocations = Buffer(device, testLocSize);
  auto testResults = Buffer(device, 4);
  auto shuffledWorkgroups = Buffer(device, params["maxWorkgroups"]);
  auto barrier = Buffer(device, 1);
  auto scratchpad = Buffer(device, params["scratchMemorySize"]);
  auto scratchLocations = Buffer(device, params["maxWorkgroups"]);
  auto stressParams = Buffer(device, 12);
  setStaticStressParams(stressParams, params);
  vector<Buffer> buffers = {testLocations, testResults, shuffledWorkgroups, barrier, scratchpad, scratchLocations, stressParams};

  // run iterations
  chrono::time_point<std::chrono::system_clock> start, end;
  start = chrono::system_clock::now();
  for (int i = 0; i < params["testIterations"]; i++) {
    auto program = Program(device, shader_file.c_str(), buffers);
    int numWorkgroups = setNumWorkgroups(params);
    clearMemory(testLocations, testLocSize);
    clearMemory(testResults, 4);
    clearMemory(barrier, 1);
    clearMemory(scratchpad, params["scratchMemorySize"]);
    setShuffledWorkgroups(shuffledWorkgroups, numWorkgroups, params["shufflePct"]);
    setScratchLocations(scratchLocations, numWorkgroups, params);
    setDynamicStressParams(stressParams, params);
    program.setWorkgroups(numWorkgroups);
    program.setWorkgroupSize(workgroupSize);
    program.prepare();
    program.run();
    cout << "Iteration " << i << "\n";
    cout << "r0 == 0 && r1 == 0: " << testResults.load(0) << "\n";
    cout << "r0 == 1 && r1 == 1: " << testResults.load(1) << "\n";
    cout << "r0 == 0 && r1 == 1: " << testResults.load(2) << "\n";
    cout << "r0 == 1 && r1 == 0: " << testResults.load(3) << "\n";
    cout << "\n";
    program.teardown();
  }
  for (Buffer buffer : buffers) {
    buffer.teardown();
  }
  device.teardown();
  instance.teardown();
}

map<string, int> read_config(string &config_file)
{
  map<string, int> m;
  ifstream in_file(config_file);
  string line;
  while (getline(in_file, line))
  {
    istringstream is_line(line);
    string key;
    if (getline(is_line, key, '='))
    {
      string value;
      if (getline(is_line, value))
      {
        m[key] = stoi(value);
      }
    }
  }
  return m;
}

void print_help()
{
  cout << "Usage: ./TestRunner shaderFile paramFile\n";
}

int main(int argc, char *argv[])
{
  if (argc < 3)
  {
    print_help();
  }
  else
  {
    srand(time(NULL));
    string shaderFile(argv[1]);
    string configFile(argv[2]);
    map<string, int> params = read_config(configFile);
     for (const auto& [key, value] : params) {
        std::cout << key << " = " << value << "; ";
    }
    std::cout << "\n";
    run(shaderFile, params);
  }
  return 0;
}
