#include <vuh/array.hpp>
#include <vuh/vuh.h>
#include <vector>
#include <set>
#include <string>

const int minWorkgroups = 4;
const int maxWorkgroups = 36;
const int minWorkgroupSize = 1;
const int maxWorkgroupSize = 1024;
const char* testName = "test";

using Array = vuh::Array<uint32_t,vuh::mem::Host>;
class ProgressTester {

public:
    void run() {
        // setup devices, memory, and parameters
        auto instance = vuh::Instance();
        auto device = instance.devices().at(0);
        auto testMemory = Array(device, maxWorkgroups*maxWorkgroupSize);
        using SpecConstants = vuh::typelist<uint32_t>;
	std::string testFile(testName);
	testFile = testFile + ".spv";
	for (int i = 0; i < 10; i++) {
	    printf("\ntest iteration %i\n", i);
	    int numWorkgroups = setNumWorkgroups();
	    int workgroupSize = setWorkgroupSize();
	    printf("number of workgroups: %i\n", numWorkgroups);
	    printf("workgroup size: %i\n", workgroupSize);
	    int size = numWorkgroups*workgroupSize;
            clearMemory(testMemory, size);
            auto program = vuh::Program<SpecConstants>(device, testFile.c_str());
            program.grid(numWorkgroups).spec(workgroupSize)(testMemory);
	    for (int i = 0; i < size; i++) {
		    if (testMemory[i] != 1) {
			    printf("%ith memory location is %i, which is not equal to 1\n", i, testMemory[i]);
			    break;
		    }
	    }
	}
    }

    void clearMemory(Array &gpuMem, int size) {
	for (int i = 0; i < size; i++) {
		gpuMem[i] = 0;
	}
    }
    
    int setWorkgroupSize() {
	if (minWorkgroupSize == maxWorkgroupSize) {
	    return minWorkgroupSize;
	} else {
 	    int size = rand() % (maxWorkgroupSize - minWorkgroupSize);
            return minWorkgroupSize + size;
	}
    }

    int setNumWorkgroups() {
	if (minWorkgroups == maxWorkgroups) {
	    return minWorkgroups;
	} else {
	    int size = rand() % (maxWorkgroups - minWorkgroups);
            return minWorkgroups + size;
	}
    }
};

int main(int argc, char* argv[]) {
    srand (time(NULL));
    ProgressTester app;
    try {
        app.run();
    }
    catch (const std::runtime_error& e) {
        printf("%s\n", e.what());
        return 1;
    }
    return 0;
}


