#include <vector>
#include <set>
#include <string>
#include <chrono>
#include <iostream>
#include "easyvk.h"

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
const int memStressIterations = {{ memStressIterations }};
const int memStressPattern = {{ memStressPattern }};
const int preStressPct = {{ preStressPct }};
const int preStressIterations = {{ preStressIterations }};
const int preStressPattern = {{ preStressPattern }};
const int stressLineSize = {{ stressLineSize }};
const int stressTargetLines = {{ stressTargetLines }};
const int gpuDeviceId = {{ gpuDeviceId }};
const char* testName = "{{ testName }}";
const char* weakBehaviorStr = "{{ weakBehaviorStr }}";
const int testIterations = {{ testIterations }};
int weakBehavior = 0;
int nonWeakBehavior = 0;
const int sampleInterval = 1000;

class LitmusTester {

private:
    typedef enum StressAssignmentStrategy {ROUND_ROBIN, CHUNKING} StressAssignmentStrategy;
    StressAssignmentStrategy stressAssignmentStrategy = {{ stressAssignmentStrategy }};

public:
    void run() {
	    printf("Starting %s litmus test run\n", testName);
	    auto instance = easyvk::Instance(false);
	    auto device = getDevice(&instance);
	    printf("Weak behavior to watch for: %s\n", weakBehaviorStr);
	    printf("Sampling output approximately every %i iterations\n", sampleInterval);
	    // setup devices, memory, and parameters
	    auto testData = easyvk::Buffer(device, testMemorySize);
	    auto memLocations = easyvk::Buffer(device, numMemLocations);
	    auto results = easyvk::Buffer(device, numOutputs);
	    auto shuffleIds = easyvk::Buffer(device, maxWorkgroups*maxWorkgroupSize);
	    auto barrier = easyvk::Buffer(device, 1);
	    auto scratchpad = easyvk::Buffer(device, scratchMemorySize);
	    auto scratchLocations = easyvk::Buffer(device, maxWorkgroups);
	    auto stressParams = easyvk::Buffer(device, 7);
	    std::vector<easyvk::Buffer> testBuffers = {testData, memLocations, results, shuffleIds, barrier, scratchpad, scratchLocations, stressParams};
	    std::string testFile(testName);
	    testFile = "target/" + testFile + ".spv";
	    
	    std::chrono::time_point<std::chrono::system_clock> start, end;
	    start = std::chrono::system_clock::now();
	    for (int i = 0; i < testIterations; i++) {
		    auto program = easyvk::Program(device, testFile.c_str(), testBuffers);
		    int numWorkgroups = setNumWorkgroups();
		    int workgroupSize = setWorkgroupSize();
		    clearMemory(testData, testMemorySize);
		    setMemLocations(memLocations);
		    clearMemory(results, numOutputs);
		    setShuffleIds(shuffleIds, numWorkgroups, workgroupSize);
		    clearMemory(barrier, 1);
		    clearMemory(scratchpad, scratchMemorySize);
		    setScratchLocations(scratchLocations, numWorkgroups);
		    setStressParams(stressParams);
		    program.setWorkgroups(numWorkgroups);
		    program.setWorkgroupSize(workgroupSize);
		    program.prepare();
		    program.run();
		    checkResult(testData, results, memLocations);
		    program.teardown();
	    }
	    end = std::chrono::system_clock::now();
	    std::chrono::duration<double> elapsed_seconds = end - start;
	    std::cout << "elapsed time: " << elapsed_seconds.count() << "s\n"; 
	    std::cout << "iterations per second: " << testIterations / elapsed_seconds.count() << " \n";
	    for (easyvk::Buffer buffer : testBuffers) {
		    buffer.teardown();
	    }
	    device.teardown();
	    instance.teardown();
    }

    easyvk::Device getDevice(easyvk::Instance* instance) {
	    int idx = 0;
	    if (gpuDeviceId != -1) {
		    int j = 0;
		    for (easyvk::Device _device : instance->devices()) {
			    if (_device.properties().deviceID == gpuDeviceId) {	
				    idx = j;
				    break;
			    }
			    j++;
		    }
	    }
	    easyvk::Device device = instance->devices().at(idx);
	    printf("Using device %s\n", device.properties().deviceName);
	    return device;
    }

    void checkResult(easyvk::Buffer &testData, easyvk::Buffer &results, easyvk::Buffer &memLocations) {
	if (rand() % sampleInterval == 1) {
	    {{ postConditionSample }}
	}
        if ({{ postCondition }}) {
            weakBehavior++;
        } else {
            nonWeakBehavior++;
        }
    }

    void clearMemory(easyvk::Buffer &gpuMem, int size) {
	    for (int i = 0; i < size; i++) {
		    gpuMem.store(i, 0);
	    }
    }
    
    void setShuffleIds(easyvk::Buffer &ids, int numWorkgroups, int workgroupSize) {
        // initialize identity mapping
        for (int i = 0; i < numWorkgroups*workgroupSize; i++) {
		ids.store(i, i);
        }
        if (percentageCheck(shufflePct)) {
            // shuffle workgroups
            for (int i = numWorkgroups - 1; i >= 0; i--) {
                int x = rand() % (i + 1);
                if (workgroupSize > 1) {
                    // swap and shuffle invocations within a workgroup
                    for (int j = 0; j < workgroupSize; j++) {
                        uint32_t temp = ids.load(i*workgroupSize + j);
                        ids.store(i*workgroupSize + j, ids.load(x*workgroupSize + j));;
                        ids.store(x*workgroupSize + j, temp);
                    }
                    for (int j = workgroupSize - 1; j > 0; j--) {
                        int y = rand() % (j + 1);
                        uint32_t temp = ids.load(i * workgroupSize + y);
                        ids.store(i * workgroupSize + y, ids.load(i * workgroupSize + j));
                        ids.store(i * workgroupSize + j, temp);
                    }
                } else {
                    uint32_t temp = ids.load(i);
                    ids.store(i, ids.load(x));
                    ids.store(x, temp);
                }
            }
        }
    }

    void setMemLocations(easyvk::Buffer &locations) {
	    std::set<int> usedRegions;
        int numRegions = testMemorySize / memStride;
        for (int i = 0; i < numMemLocations; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
            region = rand() % numRegions;
            int locInRegion = rand() % (memStride);
            locations.store(i, (region * memStride) + locInRegion);
            usedRegions.insert(region);
        }
    }

    /** Sets the stress regions and the location in each region to be stressed. Uses the stress assignment strategy to assign
     * workgroups to specific stress locations. 
     */
    void setScratchLocations(easyvk::Buffer &locations, int numWorkgroups) {
	    std::set <int> usedRegions;
        int numRegions = scratchMemorySize / stressLineSize;
        for (int i = 0; i < stressTargetLines; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
            region = rand() % numRegions;
            int locInRegion = rand() % (stressLineSize);
            switch (stressAssignmentStrategy) {
                case ROUND_ROBIN:
                    for (int j = i; j < numWorkgroups; j += stressTargetLines) {
                        locations.store(j, (region * stressLineSize) + locInRegion);
                    }
                    break;
                case CHUNKING:
                    int workgroupsPerLocation = numWorkgroups/stressTargetLines;
                    for (int j = 0; j < workgroupsPerLocation; j++) {
                        locations.store(i*workgroupsPerLocation + j, (region * stressLineSize) + locInRegion);
                    }
                    if (i == stressTargetLines - 1 && numWorkgroups % stressTargetLines != 0) {
                        for (int j = 0; j < numWorkgroups % stressTargetLines; j++) {
                            locations.store(numWorkgroups - j - 1, (region * stressLineSize) + locInRegion);
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

    /**
     * 0: barrier
     * 1: memory stress
     * 2: memory stress iterations
     * 3: memory stress pattern
     * 4: pre-stress
     * 5: pre-stress iterations
     * 6: pre-stress pattern
     */
    void setStressParams(easyvk::Buffer &params) {
        if (percentageCheck(barrierPct)) {
	    params.store(0, 1);
        } else {
	    params.store(0, 0);
	}
        if (percentageCheck(memStressPct)) {
            params.store(1, 1);
        } else {
	    params.store(1, 0);
        }
	params.store(2, memStressIterations);
	params.store(3, memStressPattern);
        if (percentageCheck(preStressPct)) {
	    params.store(4, 1);
        } else {
	    params.store(4, 0);
        }
	params.store(5, preStressIterations);
	params.store(6, preStressPattern);
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
