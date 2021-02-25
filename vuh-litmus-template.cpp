#include <vuh/array.hpp>
#include <vuh/vuh.h>
#include <vector>
#include <set>
#include <string>
#include <chrono>
#include <iostream>

const int minWorkgroups = {{ minWorkgroups }};
const int maxWorkgroups = {{ maxWorkgroups }};
const int minWorkgroupSize = {{ minWorkgroupSize }};
const int maxWorkgroupSize = {{ maxWorkgroupSize }};
const int shufflePct = {{ shufflePct }};
const int barrierPct = {{ barrierPct }};
const int numMemLocations = {{ numMemLocations }};
const int testMemorySize = {{ testMemorySize }};
const int numOutputs = {{ numOutputs }};
const int scratchMemorySize = {{ scratchMemorySize }};
const int memStride = {{ memStride }};
const int memStressPct = {{ memStressPct }};
const int preStressPct = {{ preStressPct }};
const int stressLineSize = {{ stressLineSize }};
const int stressTargetLines = {{ stressTargetLines }};
const int gpuDeviceId = {{ gpuDeviceId }};
const char* testName = "{{ testName }}";
const char* weakBehaviorStr = "{{ weakBehaviorStr }}";
const int testIterations = {{ testIterations }};
int weakBehavior = 0;
int nonWeakBehavior = 0;
const int sampleInterval = 1000;

using Array = vuh::Array<uint32_t,vuh::mem::Host>;
class LitmusTester {

private:
    typedef enum StressAssignmentStrategy {ROUND_ROBIN, CHUNKING} StressAssignmentStrategy;
    StressAssignmentStrategy stressAssignmentStrategy = {{ stressAssignmentStrategy }};

public:
    void run() {
	printf("Starting %s litmus test run\n", testName);
        auto instance = vuh::Instance();
	auto device = getDevice(&instance);
	printf("Weak behavior to watch for: %s\n", weakBehaviorStr);
	printf("Sampling output approximately every %i iterations\n", sampleInterval);
        // setup devices, memory, and parameters
        auto testData = Array(device, testMemorySize/sizeof(uint32_t));
	auto memLocations = Array(device, numMemLocations);
        auto results = Array(device, numOutputs);
        auto shuffleIds = Array(device, maxWorkgroups*maxWorkgroupSize);
        auto barrier = Array(device, 1);
        auto scratchpad = Array(device, scratchMemorySize/sizeof(uint32_t));
        auto scratchLocations = Array(device, maxWorkgroups);
	auto stressParams = Array(device, 3);
        using SpecConstants = vuh::typelist<uint32_t>;
	std::string testFile(testName);
	testFile = testFile + ".spv";
        
	std::chrono::time_point<std::chrono::system_clock> start, end;
	start = std::chrono::system_clock::now();
	for (int i = 0; i < testIterations; i++) {
	    auto program = vuh::Program<SpecConstants>(device, testFile.c_str());
	    int numWorkgroups = setNumWorkgroups();
	    int workgroupSize = setWorkgroupSize();
            clearMemory(testData, testMemorySize/sizeof(uint32_t));
	    setMemLocations(memLocations);
            clearMemory(results, numOutputs);
            setShuffleIds(shuffleIds, numWorkgroups, workgroupSize);
            clearMemory(barrier, 1);
            clearMemory(scratchpad, scratchMemorySize/sizeof(uint32_t));
            setScratchLocations(scratchLocations, numWorkgroups);
	    setStressParams(stressParams);
            program.grid(numWorkgroups).spec(workgroupSize)(testData, memLocations, results, shuffleIds, barrier, scratchpad, scratchLocations, stressParams);
            checkResult(testData, results, memLocations);
	}
	end = std::chrono::system_clock::now();
	std::chrono::duration<double> elapsed_seconds = end - start;
	std::cout << "elapsed time: " << elapsed_seconds.count() << "s\n"; 
	std::cout << "iterations per second: " << testIterations / elapsed_seconds.count() << " \n";
    }

    vuh::Device getDevice(vuh::Instance* instance) {
	vuh::Device device = instance->devices().at(0);
	if (gpuDeviceId != -1) {
	    for (vuh::Device _device : instance->devices()) {
		if (_device.properties().deviceID == gpuDeviceId) {
		    device = _device;
		    break;
		}
	    }
	}
	printf("Using device %s\n", device.properties().deviceName);
	return device;
    }

    void checkResult(Array &testData, Array &results, Array &memLocations) {
	if (rand() % sampleInterval == 1) {
	    {{ postConditionSample }}
	}
        if ({{ postCondition }}) {
            weakBehavior++;
        } else {
            nonWeakBehavior++;
        }
    }

    void clearMemory(Array &gpuMem, int size) {
	for (int i = 0; i < size; i++) {
		gpuMem[i] = 0;
	}
    }
    
    void setShuffleIds(Array &ids, int numWorkgroups, int workgroupSize) {
        // initialize identity mapping
        for (int i = 0; i < numWorkgroups*workgroupSize; i++) {
            ids[i] = i;
        }
        if (percentageCheck(shufflePct)) {
            // shuffle workgroups
            for (int i = numWorkgroups - 1; i >= 0; i--) {
                int x = rand() % (i + 1);
                if (workgroupSize > 1) {
                    // swap and shuffle invocations within a workgroup
                    for (int j = 0; j < workgroupSize; j++) {
                        uint32_t temp = ids[i*workgroupSize + j];
                        ids[i*workgroupSize + j] = ids[x*workgroupSize + j];
                        ids[x*workgroupSize + j] = temp;
                    }
                    for (int j = workgroupSize - 1; j > 0; j--) {
                        int y = rand() % (j + 1);
                        uint32_t temp = ids[i * workgroupSize + y];
                        ids[i * workgroupSize + y] = ids[i * workgroupSize + j];
                        ids[i * workgroupSize + j] = temp;
                    }
                } else {
                    uint32_t temp = ids[i];
                    ids[i] = ids[x];
                    ids[x] = temp;
                }
            }
        }
    }

    void setMemLocations(Array &locations) {
	std::set<int> usedRegions;
        int numRegions = testMemorySize / memStride;
        for (int i = 0; i < numMemLocations; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
                region = rand() % numRegions;
            int locInRegion = rand() % (memStride/sizeof(uint32_t));
            locations[i] = (region * memStride)/sizeof(uint32_t) + locInRegion;
            usedRegions.insert(region);
        }
    }

    /** Sets the stress regions and the location in each region to be stressed. Uses the stress assignment strategy to assign
     * workgroups to specific stress locations. 
     */
    void setScratchLocations(Array &locations, int numWorkgroups) {
	std::set <int> usedRegions;
        int numRegions = scratchMemorySize / stressLineSize;
        for (int i = 0; i < stressTargetLines; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
                region = rand() % numRegions;
            int locInRegion = rand() % (stressLineSize/sizeof(uint32_t));
            switch (stressAssignmentStrategy) {
                case ROUND_ROBIN:
                    for (int j = i; j < numWorkgroups; j += stressTargetLines) {
                        locations[j] = (region * stressLineSize)/sizeof(uint32_t) + locInRegion;
                    }
                    break;
                case CHUNKING:
                    int workgroupsPerLocation = numWorkgroups/stressTargetLines;
                    for (int j = 0; j < workgroupsPerLocation; j++) {
                        locations[i*workgroupsPerLocation + j] = (region * stressLineSize)/sizeof(uint32_t) + locInRegion;
                    }
                    if (i == stressTargetLines - 1 && numWorkgroups % stressTargetLines != 0) {
                        for (int j = 0; j < numWorkgroups % stressTargetLines; j++) {
                            locations[numWorkgroups - j - 1] = (region * stressLineSize)/sizeof(uint32_t) + locInRegion;
                        }
                    }
                    break;
            }
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

    void setStressParams(Array &params) {
        if (percentageCheck(memStressPct)) {
            params[0] = 1;
        } else {
            params[0] = 0;
        }
        if (percentageCheck(preStressPct)) {
            params[1] = 1;
        } else {
            params[1] = 0;
        }
        if (percentageCheck(barrierPct)) {
            params[2] = 1;
        } else {
            params[2] = 0;
        }
    }

    bool percentageCheck(int percentage) {
        return rand() % 100 < percentage;
    }
};

int main(int argc, char* argv[]) {
    srand (time(NULL));
    LitmusTester app;
    try {
        app.run();
        printf("weak behavior: %d\n", weakBehavior);
        printf("non weak behavior: %d\n", nonWeakBehavior);
    }
    catch (const std::runtime_error& e) {
        printf("%s\n", e.what());
        return 1;
    }
    return 0;
}


