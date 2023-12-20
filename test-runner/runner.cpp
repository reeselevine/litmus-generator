#include <map>
#include <set>
#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
#include <chrono>
#include <easyvk.h>
#include <unistd.h>
#include "checker.h"

using namespace std;
using namespace easyvk;

/** Returns the GPU to use for this test run. Users can specify the specific GPU to use
 *  with the a device index parameter. If the index is too large, an error is returned.
 */
Device getDevice(Instance &instance, int device_idx) {
  Device device = Device(instance, instance.physicalDevices().at(device_idx));
  cout << "Using device " << device.properties.deviceName << "\n";
  return device;
}

void listDevices() {
  auto instance = Instance(false);
  int i = 0;
  for (auto physicalDevice : instance.physicalDevices()) {
    Device device = Device(instance, physicalDevice);
    cout << "Device: " << device.properties.deviceName << " ID: " << device.properties.deviceID << " Index: " << i << "\n";
    i++;
  }
}

/** Zeroes out the specified buffer. */
void clearMemory(Buffer &gpuMem, int size) {
  for (int i = 0; i < size; i++) {
    gpuMem.store<uint32_t>(i, 0);
  }
}

/** Checks whether a random value is less than a given percentage. Used for parameters like memory stress that should only
 *  apply some percentage of iterations.
 */
bool percentageCheck(int percentage) {
  return rand() % 100 < percentage;
}

/** Assigns shuffled workgroup ids, using the shufflePct to determine whether the ids should be shuffled this iteration. */
void setShuffledWorkgroups(Buffer &shuffledWorkgroups, int numWorkgroups, int shufflePct) {
  for (int i = 0; i < numWorkgroups; i++) {
    shuffledWorkgroups.store<uint32_t>(i, i);
  }
  if (percentageCheck(shufflePct)) {
    for (int i = numWorkgroups - 1; i > 0; i--) {
      int swap = rand() % (i + 1);
      int temp = shuffledWorkgroups.load<uint32_t>(i);
      shuffledWorkgroups.store<uint32_t>(i, shuffledWorkgroups.load<uint32_t>(swap));
      shuffledWorkgroups.store<uint32_t>(swap, temp);
    }
  }
}

/** Sets the stress regions and the location in each region to be stressed. Uses the stress assignment strategy to assign
  * workgroups to specific stress locations. Assignment strategy 0 corresponds to a "round-robin" assignment where consecutive
  * threads access separate scratch locations, while assignment strategy 1 corresponds to a "chunking" assignment where a group
  * of consecutive threads access the same location.
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
          locations.store<uint32_t>(j, (region * params["stressLineSize"]) + locInRegion);
        }
        break;
      case 1:
        int workgroupsPerLocation = numWorkgroups/params["stressTargetLines"];
        for (int j = 0; j < workgroupsPerLocation; j++) {
          locations.store<uint32_t>(i*workgroupsPerLocation + j, (region * params["stressLineSize"]) + locInRegion);
        }
        if (i == params["stressTargetLines"] - 1 && numWorkgroups % params["stressTargetLines"] != 0) {
          for (int j = 0; j < numWorkgroups % params["stressTargetLines"]; j++) {
            locations.store<uint32_t>(numWorkgroups - j - 1, (region * params["stressLineSize"]) + locInRegion);
          }
        }
        break;
    }
  }
}

/** These parameters vary per iteration, based on a given percentage. */
void setDynamicStressParams(Buffer &stressParams, map<string, int> params) {
  if (percentageCheck(params["barrierPct"])) {
    stressParams.store<uint32_t>(0, 1);
  } else {
    stressParams.store<uint32_t>(0, 0);
  }  
  if (percentageCheck(params["memStressPct"])) {
    stressParams.store<uint32_t>(1, 1);
  } else {
    stressParams.store<uint32_t>(1, 0);
  }  
  if (percentageCheck(params["preStressPct"])) {
    stressParams.store<uint32_t>(4, 1);
  } else {
    stressParams.store<uint32_t>(4, 0);
  }
}

/** These parameters are static for all iterations of the test. Aliased memory is used for coherence tests. */
void setStaticStressParams(Buffer &stressParams, map<string, int> stress_params, map<string, int> test_params) {
  stressParams.store<uint32_t>(2, stress_params["memStressIterations"]);
  stressParams.store<uint32_t>(3, stress_params["memStressPattern"]);
  stressParams.store<uint32_t>(5, stress_params["preStressIterations"]);
  stressParams.store<uint32_t>(6, stress_params["preStressPattern"]);
  stressParams.store<uint32_t>(7, stress_params["permuteThread"]);
  stressParams.store<uint32_t>(8, test_params["permuteLocation"]);
  stressParams.store<uint32_t>(9, stress_params["testingWorkgroups"]);
  stressParams.store<uint32_t>(10, stress_params["memStride"]);
  if (test_params["aliasedMemory"] == 1) {
    stressParams.store(11, 0);
  } else {
    stressParams.store(11, stress_params["memStride"]);
  }
}

/** Returns a value between the min and max. */
int setBetween(int min, int max) {
  if (min == max) {
    return min;
  } else {
    int size = rand() % (max - min);
    return min + size;
  }
}

/** A test consists of N iterations of a shader and its corresponding result shader. */
void run(string test_name, string &shader_file, string &result_shader_file, map<string, int> stress_params, map<string, int> test_params, int device_id, bool enable_validation_layers)
{
  // initialize settings
  auto instance = Instance(enable_validation_layers);
  auto device = getDevice(instance, device_id);
  int testingThreads = stress_params["workgroupSize"] * stress_params["testingWorkgroups"];
  int testLocSize = testingThreads * test_params["numMemLocations"] * stress_params["memStride"];

  // set up buffers
  vector<Buffer> buffers;
  vector<Buffer> resultBuffers;
  auto testLocations = Buffer(device, testLocSize, sizeof(uint32_t));
  if (!test_params["workgroupMemory"] == 1 || test_params["checkMemory"] == 1) { // test shader needs a test locations buffer for device memory tests, or if we need to save workgroup memory
    buffers.push_back(testLocations);
  }
  resultBuffers.push_back(testLocations);
 
  auto readResults = Buffer(device, test_params["numOutputs"] * testingThreads, sizeof(uint32_t));
  buffers.push_back(readResults);
  resultBuffers.push_back(readResults);

  auto testResults = Buffer(device, test_params["numResults"], sizeof(uint32_t));

  resultBuffers.push_back(testResults);
  auto shuffledWorkgroups = Buffer(device, stress_params["maxWorkgroups"], sizeof(uint32_t));
  buffers.push_back(shuffledWorkgroups);
  auto barrier = Buffer(device, 1, sizeof(uint32_t));
  buffers.push_back(barrier);
  auto scratchpad = Buffer(device, stress_params["scratchMemorySize"], sizeof(uint32_t));
  buffers.push_back(scratchpad);
  auto scratchLocations = Buffer(device, stress_params["maxWorkgroups"], sizeof(uint32_t));
  buffers.push_back(scratchLocations);
  auto stressParams = Buffer(device, 12, sizeof(uint32_t));
  setStaticStressParams(stressParams, stress_params, test_params);
  buffers.push_back(stressParams);
  resultBuffers.push_back(stressParams);

  // run iterations
  chrono::time_point<std::chrono::system_clock> start, end;
  start = chrono::system_clock::now();
  int weakBehaviors = 0;
  int totalBehaviors = 0;
  
  float testTime = 0;

  for (int i = 0; i < stress_params["testIterations"]; i++) {
    auto program = Program(device, shader_file.c_str(), buffers);
    auto resultProgram = Program(device, result_shader_file.c_str(), resultBuffers);

    int numWorkgroups = setBetween(stress_params["testingWorkgroups"], stress_params["maxWorkgroups"]);
    if (!test_params["workgroupMemory"] == 1 || test_params["checkMemory"] == 1) {
      clearMemory(testLocations, testLocSize); // test locations will be the first buffer
    }
    clearMemory(testResults, test_params["numResults"]);
    clearMemory(barrier, 1);
    clearMemory(scratchpad, stress_params["scratchMemorySize"]);
    setShuffledWorkgroups(shuffledWorkgroups, numWorkgroups, stress_params["shufflePct"]);
    setScratchLocations(scratchLocations, numWorkgroups, stress_params);
    setDynamicStressParams(stressParams, stress_params);

    program.setWorkgroups(numWorkgroups);
    resultProgram.setWorkgroups(stress_params["testingWorkgroups"]);
    program.setWorkgroupSize(stress_params["workgroupSize"]);
    resultProgram.setWorkgroupSize(stress_params["workgroupSize"]);

    // workgroup memory shaders use workgroup memory for testing
    if (test_params["workgroupMemory"] == 1) {
      program.setWorkgroupMemoryLength(testLocSize*sizeof(uint32_t), 0);
      program.setWorkgroupMemoryLength(testLocSize*sizeof(uint32_t), 1);
    }

    program.initialize("litmus_test");
    testTime += program.runWithDispatchTiming();
    resultProgram.initialize("litmus_test");
    resultProgram.run();

    cout << "Iteration " << i << "\n";
    vector<uint32_t> results;
    for (int i = 0; i < test_params["numResults"]; i++) {
      results.push_back(testResults.load<uint32_t>(i));
      totalBehaviors += testResults.load<uint32_t>(i);
    }
    weakBehaviors += check_results(results, test_name);


    program.teardown();
    resultProgram.teardown();
  }

  
  float testTimeMs = testTime/1000000;
  
  cout << "Total test shader time: " << testTimeMs << " ms\n";
  cout << "Weak behavior rate: " << float(weakBehaviors)/(testTimeMs/1000) << " per second\n";
  cout << "Weak behavior percentage: " << float(weakBehaviors)/float(totalBehaviors) * 100 << "%\n";
  cout << "Number of weak behaviors: " << weakBehaviors << "\n";

  for (Buffer buffer : buffers) {
    buffer.teardown();
  }
  testResults.teardown();
  device.teardown();
  instance.teardown();
}

/** Reads a specified config file and stores the parameters in a map. Parameters should be of the form "key=value", one per line. */
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

int main(int argc, char *argv[])
{

  string shaderFile;
  string resultShaderFile;
  string stressParamsFile;
  string testParamsFile;
  string testName;
  int deviceIndex = 0;
  bool enableValidationLayers = false;
  bool list_devices = false;

  int c;
  while ((c = getopt(argc, argv, "vcls:r:p:t:d:n:")) != -1)
    switch (c)
    {
    case 'n':
      testName = optarg;
      break;
    case 's':
      shaderFile = optarg;
      break;
    case 'r':
      resultShaderFile = optarg;
      break;
    case 'p':
      stressParamsFile = optarg;
      break;
    case 't':
      testParamsFile = optarg;
      break;
    case 'v':
      enableValidationLayers = true;
      break;
    case 'l':
      list_devices = true;
      break;
    case 'd':
      deviceIndex = atoi(optarg);
      break;
    case '?':
      if (optopt == 's' || optopt == 'r' || optopt == 'p')
        std::cerr << "Option -" << optopt << "requires an argument\n";
      else
        std::cerr << "Unknown option" << optopt << "\n";
      return 1;
    default:
      abort();
    }

  if (list_devices) {
    listDevices();
    return 0;
  }

  if (testName.empty()) {
    std::cerr << "Test name (-n) must be set\n";
    return 1;
  }    

  if (shaderFile.empty()) {
    std::cerr << "Shader (-s) must be set\n";
    return 1;
  }    

   if (resultShaderFile.empty()) {
    std::cerr << "Result shader (-r) must be set\n";
    return 1;
  }    

  if (stressParamsFile.empty()) {
    std::cerr << "Stress param file (-p) must be set\n";
    return 1;
  }    
 
  if (testParamsFile.empty()) {
    std::cerr << "Test param file (-t) must be set\n";
    return 1;
  }    

  srand(time(NULL));
  map<string, int> stressParams = read_config(stressParamsFile);
  map<string, int> testParams = read_config(testParamsFile);
  run(testName, shaderFile, resultShaderFile, stressParams, testParams, deviceIndex, enableValidationLayers);
  return 0;
}
