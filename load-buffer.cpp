#include <vuh/array.hpp>
#include <vuh/vuh.h>
#include <vector>
#include <set>
#include <string>

const int minWorkgroups = 4;
const int maxWorkgroups = 36;
const int minWorkgroupSize = 1;
const int maxWorkgroupSize = 1024;
const int shufflePct = 100;
const int barrierPct = 85;
const int numMemLocations = 2;
const int testMemorySize = 1024;
const int numOutputs = 2;
const int scratchMemorySize = 4096;
const int memStride = 64;
const int memStressPct = 100;
const int preStressPct = 100;
const int stressLineSize = 256;
const int stressTargetLines = 2;
const char* testName = "load-buffer";
const char* weakBehaviorStr = "r0: 1, r1: 1";
int weakBehavior = 0;
int nonWeakBehavior = 0;

using Array = vuh::Array<uint32_t,vuh::mem::Host>;
class LitmusTester {

private:
    typedef enum StressAssignmentStrategy {ROUND_ROBIN, CHUNKING} StressAssignmentStrategy;
    StressAssignmentStrategy stressAssignmentStrategy = ROUND_ROBIN;

public:
    void run() {
	printf("Running test %s\n", testName);
	printf("Weak behavior to watch for: %s\n", weakBehaviorStr);
        // setup devices, memory, and parameters
        auto instance = vuh::Instance();
        auto device = instance.devices().at(0);
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
        
	for (int i = 0; i < 10000; i++) {
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
    }

    void checkResult(Array &testData, Array &results, Array &memLocations) {
	if (rand() % 1000 == 1) {
	    printf("r0: %u, r1: %u\n", results[0],results[1]);
	}
        if (results[0] == 1 && results[1] == 1) {
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


