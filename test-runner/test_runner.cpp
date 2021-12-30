#include <map>
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

void clearMemory(easyvk::Buffer &gpuMem, int size) {
  for (int i = 0; i < size; i++) {
    gpuMem.store(i, 0);
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
  auto instance = easyvk::Instance(false);
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
    program.teardown();
  }
  for (Buffer buffer : buffers) {
    buffer.teardown();
  }

  auto a = easyvk::Buffer(device, size);
  auto b = easyvk::Buffer(device, size);
  auto c = easyvk::Buffer(device, size);
  for (int i = 0; i < size; i++)
  {
    a.store(i, i);
    b.store(i, i + 1);
    c.store(i, 0);
  }
  std::vector<easyvk::Buffer> bufs = {a, b, c};
  auto program = easyvk::Program(device, shader_file.c_str(), bufs);
  program.setWorkgroups(size);
  program.setWorkgroupSize(1);
  program.prepare();
  program.run();
  for (int i = 0; i < size; i++)
  {
    std::cout << "c[" << i << "]: " << c.load(i) << "\n";
    assert(c.load(i) == a.load(i) + b.load(i));
  }
  program.teardown();
  a.teardown();
  b.teardown();
  c.teardown();
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
