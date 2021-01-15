#include <vuh/array.cpp>
#include <vuh/vuh.h>
#include <vector>

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
int weakBehavior = 0;
int nonWeakBehavior = 0;

class LitmusTester {

    struct PushConstants {
        int[4] regionOffset;
        int[4] regionGroupOffset;
        int _memStress;
        int _preStress;
        int _useBarrier;
        int memLocations[numMemLocations];

        PushConstants(int ms, int ps, int ub, int[] locations) {
            _memStress = ms;
            _preStress = ps;
            _useBarrier = ub;
            for (int i = 0; i < numMemLocations; i++) {
                memLocations[i] = locations[i];
            }
        }
    };

    void run() {
        // setup devices, memory, and parameters
        auto instance = vuh::Instance();
        auto device = instance.devices().at(0);
        auto testData = vuh::Arrray<uint32_t>(device, testMemorySize/sizeof(uint32_t));
        auto results = vuh::Array<uint32_t>(device, numOutputs);
        auto shuffleIds = vuh::Array<uint32_t>(device, numWorkgroups*workgroupSize);
        auto barrier = vuh::Array<uint32_t>(device, 1);
        auto scratchpad = vuh::Array<uint32_t>(device, scratchMemorySize/sizeof(uint32_t));
        auto scratchLocations = vuh::Array<uint32_t>(device, numWorkgroups);
        using SpecConstants = vuh::typelist<uint32_t>;
        auto program = vuh::Program<SpecConstants, PushConstants>(device, "load-buffer.spv");

        // initialize and run program
        clearMemory(testData, testMemorySize/sizeof(uint32_t));
        clearMemory(results, numOutputs);
        setShuffleIds(shuffleIds);
        clearMemory(barrier, 1);
        clearMemory(scratchpad, scratchMemorySize/sizeof(uint32_t));
        setScratchLocations(scratchLocations);

        PushConstants pushConstants = setPushConstants();
        int _workgroupSize = setWorkgroupSize();
        int _numWorkgroups = setNumWorkgroups();

        program.grid(_numWorkgroups).spec(_workgroupSize)(pushConstants, testData, results, shuffleIds, barrier, scratchpad, scratchLocations);
    }

    void checkResult(vuh::Array testData, vuh:Array results) {
        auto hostTestData = std::vector<uint32_t>(testMemorySize/sizeof(uint32_t), 0);
        auto hostResults = std::vector<uint32_t>(numOutputs, 0);
        testData.toHost(hostTestData.begin());
        results.toHost(hostResults.begin());
        if ({{ postCondition }}) {
            weakBehavior++;
        } else {
            nonWeakBehavior++;
        }
    }

    void clearMemory(vuh::Array gpuMem, int size) {
        auto zeros = std::vector<uint32_t>(size, 0);
        gpuMem.fromHost(zeros.begin(), zeros.end());
    }

    void setShuffleIds(vuh::Array shuffleIds) {
        // initialize identity mapping
        auto ids = std::vector<uint32_t>(numWorkgroups*workgroupSize);
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
        shuffleIds.fromHost(ids.begin(), ids.end());
    }

    /** Sets the stress regions and the location in each region to be stressed. Uses the stress assignment strategy to assign
     * workgroups to specific stress locations. 
     */
    void setScratchLocations(vuh::Array scratchLocations) {
        auto locations = vector<uint32_t>(numWorkgroups, 0);
        set <int> usedRegions;
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
        scratchLocations.fromHost(locations.begin(), locations.end());
    }

    int setWorkgroupSize() {
        return workgroupSize;
    }

    int setNumWorkgroups() {
        return numWorkgroups;
    }

    PushConstants setPushConstants() {
        int memLocations[numMemLocations];
        set<int> usedRegions;
        int numRegions = testMemorySize / memStride;
        for (int i = 0; i < numMemLocations; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
                region = rand() % numRegions;
            int locInRegion = rand() % (memStride/sizeof(uint32_t));
            memLocations[i] = (region * memStride)/sizeof(uint32_t) + locInRegion;
            usedRegions.insert(region);
        }
        PushConstants constants = PushConstants(memStress, preStress, useBarrier, memLocations);
        return constants;
    }
}

int main(int argc, char* argv[]) {
    LitmusTester app;
    try {
        app.run();
        printf("weak behavior: %d\n", weakBehavior);
        printf("non weak behavior: %d\n", nonWeakBehavior);
    }
    catch (const runtime_error& e) {
        printf("%s\n", e.what());
        return 1;
    }
    return 0;
}
