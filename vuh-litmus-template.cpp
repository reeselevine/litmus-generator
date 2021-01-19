#include <vuh/array.hpp>
#include <vuh/vuh.h>
#include <vector>
#include <set>
#include <string>

const int numWorkgroups = {{ numWorkgroups }};
const int workgroupSize = {{ workgroupSize }};
const int shuffle = {{ shuffle }};
const int barrier = {{ barrier }};
const int numMemLocations = {{ numMemLocations }};
const int testMemorySize = {{ testMemorySize }};
const int numOutputs = {{ numOutputs }};
const int scratchMemorySize = {{ scratchMemorySize }};
const int memStride = {{ memStride }};
const int memStress = {{ memStress }};
const int preStress = {{ preStress }};
const int stressLineSize = {{ stressLineSize }};
const int stressTargetLines = {{ stressTargetLines }};
const char* testName = "{{ testName }}";
int weakBehavior = 0;
int nonWeakBehavior = 0;

using Array = vuh::Array<uint32_t,vuh::mem::HostCoherent>;
class LitmusTester {

private:
    typedef enum StressAssignmentStrategy {ROUND_ROBIN, CHUNKING} StressAssignmentStrategy;
    StressAssignmentStrategy stressAssignmentStrategy = {{ stressAssignmentStrategy }};

public:
    void run() {
        // setup devices, memory, and parameters
        auto instance = vuh::Instance();
        auto device = instance.devices().at(0);
        auto testData = Array(device, testMemorySize/sizeof(uint32_t));
	auto memLocations = Array(device, numMemLocations);
        auto results = Array(device, numOutputs);
        auto shuffleIds = Array(device, numWorkgroups*workgroupSize);
        auto barrier = Array(device, 1);
        auto scratchpad = Array(device, scratchMemorySize/sizeof(uint32_t));
        auto scratchLocations = Array(device, numWorkgroups);
	auto stressParams = Array(device, 3);
        using SpecConstants = vuh::typelist<uint32_t>;
	std::string testFile(testName);
	testFile = testFile + ".spv";
        auto program = vuh::Program<SpecConstants>(device, testFile.c_str());

	for (int i = 0; i < {{ testIterations }}; i++) {

            // initialize and run program
            clearMemory(testData, testMemorySize/sizeof(uint32_t));
	    setMemLocations(memLocations);
            clearMemory(results, numOutputs);
            setShuffleIds(shuffleIds);
            clearMemory(barrier, 1);
            clearMemory(scratchpad, scratchMemorySize/sizeof(uint32_t));
            setScratchLocations(scratchLocations);
	    setStressParams(stressParams);

            int _workgroupSize = setWorkgroupSize();
            int _numWorkgroups = setNumWorkgroups();

            program.grid(_numWorkgroups).spec(_workgroupSize)(testData, memLocations, results, shuffleIds, barrier, scratchpad, scratchLocations, stressParams);
            checkResult(testData, results, memLocations);
	}
    }

    void checkResult(Array &testData, Array &results, Array &memLocations) {
	if (rand() % 1000 == 1) {
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
    
    void setShuffleIds(Array &ids) {
        // initialize identity mapping
        for (int i = 0; i < ids.size(); i++) {
            ids[i] = i;
        }
        if (shuffle) {
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
    void setScratchLocations(Array &locations) {
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
        return workgroupSize;
    }

    int setNumWorkgroups() {
        return numWorkgroups;
    }

    void setStressParams(Array &params) {
	params[0] = memStress;
	params[1] = preStress;
	params[2] = barrier;
    }
};

int main(int argc, char* argv[]) {
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
