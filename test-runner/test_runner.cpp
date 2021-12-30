#include <map>
#include <iostream>
#include <string>
#include <sstream>
#include <fstream>
#include <chrono>
#include <easyvk.h>

using namespace std;

const int size = 4;

void run(string &shader_file, map<string, string> params)
{
  auto instance = easyvk::Instance(false);
  auto device = instance.devices().at(0);
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

int setWorkgroupSize()
{
  if (minWorkgroupSize == maxWorkgroupSize)
  {
    return minWorkgroupSize;
  }
  else
  {
    int size = rand() % (maxWorkgroupSize - minWorkgroupSize);
    return minWorkgroupSize + size;
  }
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
      int value;
      if (getline(is_line, value))
      {
        m[key] = value;
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
     for (const auto& [key, value] : m) {
        std::cout << key << " = " << value << "; ";
    }
    std::cout << "\n";
    run(shaderFile, params);
  }
  return 0;
}
