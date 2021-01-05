#include <vulkan/vulkan.h>

#include <vector>
#include <set>
#include <string.h>
#include <assert.h>
#include <stdexcept>
#include <cmath>
#include <stdio.h>
#include <time.h>
using namespace std;

const int numWorkgroups = {{ numWorkgroups }};
const int workgroupSize = {{ workgroupSize }};
const int shuffle = {{ shuffle }};
const int barrier = {{ barrier }};
const int numMemLocations = {{ numMemLocations }};
const int testMemorySize = {{ testMemorySize }};
const int scratchMemorySize = {{ scratchMemorySize }};
const int memStride = {{ memStride }};
const int memStress = {{ memStress }};
int weakBehavior = 0;
int nonWeakBehavior = 0;

#ifdef NDEBUG
const bool enableValidationLayers = false;
#else
const bool enableValidationLayers = true;
#endif

#define VK_CHECK_RESULT(f) 																				\
{																										\
    VkResult res = (f);																					\
    if (res != VK_SUCCESS)																				\
    {																									\
        printf("Fatal : VkResult is %d in %s at line %d\n", res,  __FILE__, __LINE__); \
        assert(res == VK_SUCCESS);																		\
    }																									\
}

/*
 * Application repeatedly launches a shader that runs a litmus test and reports the number of times a weak memory behavior is observed.
*/
class ComputeApplication {
private:
    VkInstance instance;
    VkDebugReportCallbackEXT debugReportCallback;
    VkPhysicalDevice physicalDevice;
    VkDevice device;
    VkPipeline pipeline;
    VkPipelineLayout pipelineLayout;
    VkShaderModule computeShaderModule;
    VkCommandPool commandPool;
    VkCommandBuffer commandBuffer;
    VkDescriptorPool descriptorPool;
    VkDescriptorSet descriptorSet;
    VkDescriptorSetLayout descriptorSetLayout;

    typedef enum BufferType {TEST_DATA, RESULTS, SHUFFLE_IDS, BARRIER, SCRATCHPAD, SCRATCH_LOCATIONS, POD_ARGS} BufferType;
    /*
    Buffers that will be used in the compute shader.
    */
    struct BufferInfo {
        BufferType bufferType;
        VkBuffer buffer;
        int size; // the size of the buffer in number of memory locations
        uint32_t requiredSize; // the minimum size buffer that vulkan needs allocated in bytes
        uint32_t memOffset; // the offset within the allocated memory of this buffer
    };
    VkDeviceMemory bufferMemory;
    vector<BufferInfo> bufferInfos;
        
    vector<const char *> enabledLayers;

    VkQueue queue; // a queue supporting compute operations.
    uint32_t queueFamilyIndex;

    uint32_t shader[{{ shaderSize }}] = {{ shaderCode }};

public:
    void run() {
        srand (time(NULL));
        createInstance();
        findPhysicalDevice();
        createDevice();
        createBuffers();
        createDescriptorSetLayout();
        createDescriptorSet();
        createComputePipeline();
     	createCommandBuffer();
        for (int i = 0; i < 10000; i++) {
            initializeBuffers();
            runCommandBuffer();
            checkResult();
	    }
        cleanup();
    }

    void shuffleIds(uint32_t *ids) {
        // initialize identity mapping
        for (int i = 0; i < numWorkgroups * workgroupSize; i++) {
            ids[i] = i;
        }
        if (shuffle) {
            // shuffle workgroups
            for (int i = numWorkgroups - 1; i > 0; i--) {
                int x = rand() % (i + 1);
                if (workgroupSize > 1) {
                    // swap and shuffle invocations within a workgroup
                    for (int j = workgroupSize - 1; j > 0; j--) {
                        int y = rand() % (j + 1);
                        int z = rand() % (j + 1);
                        uint32_t temp = ids[i * workgroupSize + y];
                        ids[i * workgroupSize + y] = ids[shuffle * workgroupSize + z];
                        ids[x * workgroupSize + z] = temp;
                    }
                } else {
                    uint32_t temp = ids[i];
                    ids[i] = ids[x];
                    ids[x] = temp;
                }
            }
        }
    }

    /** Plain old data arguments are clustered into one buffer. The order is how they appear in the kernel arguments, so positions are hardcoded here. */
    void setPodArgs(uint32_t* podArgs) {
        if (memStress) {
            podArgs[0] = 1;
        }
        if (barrier) {
            podArgs[1] = 1;
        }
        // Randomizes what locations the test threads access in the test memory. Ensures a region is only used at most once. 
        set<int> usedRegions;
        int numRegions = testMemorySize / memStride;
        for (int i = 0; i < numMemLocations; i++) {
            int region = rand() % numRegions;
            while(usedRegions.count(region))
                region = rand() % numRegions;
            int locInRegion = rand() % memStride;
            podArgs[i + 2] = region * memStride + locInRegion;
            usedRegions.insert(region);
        }
    }

    void initializeBuffers() {
        uint32_t *memory = NULL;
        VK_CHECK_RESULT(vkMapMemory(device, bufferMemory, 0, VK_WHOLE_SIZE, 0, (void **)&memory));
        for (BufferInfo info : bufferInfos) {
            if (info.bufferType == SHUFFLE_IDS) {
                shuffleIds(&memory[info.memOffset]);
            } else if (info.bufferType == POD_ARGS) {
                setPodArgs(&memory[info.memOffset]);
            } else {
                for (uint32_t i = info.memOffset; i < info.requiredSize/sizeof(uint32_t); i++) {
                    memory[i] = 0;
                }
            }
        }
        vkUnmapMemory(device, bufferMemory);
    }

    static VKAPI_ATTR VkBool32 VKAPI_CALL debugReportCallbackFn(
        VkDebugReportFlagsEXT                       flags,
        VkDebugReportObjectTypeEXT                  objectType,
        uint64_t                                    object,
        size_t                                      location,
        int32_t                                     messageCode,
        const char*                                 pLayerPrefix,
        const char*                                 pMessage,
        void*                                       pUserData) {

        printf("Debug Report: %s: %s\n", pLayerPrefix, pMessage);

        return VK_FALSE;
     }

    void checkResult() {
        int32_t* data = NULL;
        VK_CHECK_RESULT(vkMapMemory(device, bufferMemory, 0, VK_WHOLE_SIZE, 0, (void **)&data));
        int32_t* output = data + bufferInfos[0].requiredSize/sizeof(uint32_t);
        int32_t* memLocations;
        for (BufferInfo info : bufferInfos) {
            if (info.bufferType == POD_ARGS) {
                memLocations = data + info.memOffset + 2;
                break;
            }
        }
        if ({{ postCondition }}) {
            weakBehavior++;
        } else {
            nonWeakBehavior++;
        }
        vkUnmapMemory(device, bufferMemory);
    }

    void createInstance() {
        vector<const char *> enabledExtensions;
        if (enableValidationLayers) {
            uint32_t layerCount;
            vkEnumerateInstanceLayerProperties(&layerCount, NULL);
            vector<VkLayerProperties> layerProperties(layerCount);
            vkEnumerateInstanceLayerProperties(&layerCount, layerProperties.data());
            bool foundLayer = false;
            for (VkLayerProperties prop : layerProperties) {
                if (strcmp("VK_LAYER_LUNARG_standard_validation", prop.layerName) == 0) {
                    foundLayer = true;
                    break;
                }
            }
            if (!foundLayer) {
                throw runtime_error("Layer VK_LAYER_LUNARG_standard_validation not supported\n");
            }
            enabledLayers.push_back("VK_LAYER_LUNARG_standard_validation");
            uint32_t extensionCount;
            vkEnumerateInstanceExtensionProperties(NULL, &extensionCount, NULL);
            vector<VkExtensionProperties> extensionProperties(extensionCount);
            vkEnumerateInstanceExtensionProperties(NULL, &extensionCount, extensionProperties.data());
            bool foundExtension = false;
            for (VkExtensionProperties prop : extensionProperties) {
                if (strcmp(VK_EXT_DEBUG_REPORT_EXTENSION_NAME, prop.extensionName) == 0) {
                    foundExtension = true;
                    break;
                }
            }
            if (!foundExtension) {
                throw runtime_error("Extension VK_EXT_DEBUG_REPORT_EXTENSION_NAME not supported\n");
            }
            enabledExtensions.push_back(VK_EXT_DEBUG_REPORT_EXTENSION_NAME);
        }		

        VkApplicationInfo applicationInfo = {};
        applicationInfo.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO;
        applicationInfo.pApplicationName = "Litmus Tester";
        applicationInfo.applicationVersion = 0;
        applicationInfo.pEngineName = "LSD Lab";
        applicationInfo.engineVersion = 0;
        applicationInfo.apiVersion = VK_API_VERSION_1_0;;
        VkInstanceCreateInfo createInfo = {};
        createInfo.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO;
        createInfo.flags = 0;
        createInfo.pApplicationInfo = &applicationInfo;
        createInfo.enabledLayerCount = enabledLayers.size();
        createInfo.ppEnabledLayerNames = enabledLayers.data();
        createInfo.enabledExtensionCount = enabledExtensions.size();
        createInfo.ppEnabledExtensionNames = enabledExtensions.data();
        VK_CHECK_RESULT(vkCreateInstance(
            &createInfo,
            NULL,
            &instance));

        if (enableValidationLayers) {
            VkDebugReportCallbackCreateInfoEXT createInfo = {};
            createInfo.sType = VK_STRUCTURE_TYPE_DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT;
            createInfo.flags = VK_DEBUG_REPORT_ERROR_BIT_EXT | VK_DEBUG_REPORT_WARNING_BIT_EXT | VK_DEBUG_REPORT_PERFORMANCE_WARNING_BIT_EXT;
            createInfo.pfnCallback = &debugReportCallbackFn;
            auto vkCreateDebugReportCallbackEXT = (PFN_vkCreateDebugReportCallbackEXT)vkGetInstanceProcAddr(instance, "vkCreateDebugReportCallbackEXT");
            if (vkCreateDebugReportCallbackEXT == nullptr) {
                throw runtime_error("Could not load vkCreateDebugReportCallbackEXT");
            }
            VK_CHECK_RESULT(vkCreateDebugReportCallbackEXT(instance, &createInfo, NULL, &debugReportCallback));
        }

    }

    void findPhysicalDevice() {
        uint32_t deviceCount;
        vkEnumeratePhysicalDevices(instance, &deviceCount, NULL);
        if (deviceCount == 0) {
            throw runtime_error("could not find a device with vulkan support");
        }
        vector<VkPhysicalDevice> devices(deviceCount);
        vkEnumeratePhysicalDevices(instance, &deviceCount, devices.data());
        for (VkPhysicalDevice device : devices) {
	    VkPhysicalDeviceProperties properties;
	    vkGetPhysicalDeviceProperties(device, &properties);
            if (properties.deviceID == 4935) { // We want the nvidia gpu on this server.
                physicalDevice = device;
            }
        }
    }

    uint32_t getComputeQueueFamilyIndex() {
        uint32_t queueFamilyCount;
        vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice, &queueFamilyCount, NULL);
        vector<VkQueueFamilyProperties> queueFamilies(queueFamilyCount);
        vkGetPhysicalDeviceQueueFamilyProperties(physicalDevice, &queueFamilyCount, queueFamilies.data());
        uint32_t i = 0;
        for (; i < queueFamilies.size(); ++i) {
            VkQueueFamilyProperties props = queueFamilies[i];
            if (props.queueCount > 0 && (props.queueFlags & VK_QUEUE_COMPUTE_BIT)) {
                break;
            }
        }
        if (i == queueFamilies.size()) {
            throw runtime_error("could not find a queue family that supports operations");
        }
        return i;
    }

    void createDevice() {
        VkDeviceQueueCreateInfo queueCreateInfo = {};
        queueCreateInfo.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO;
        queueFamilyIndex = getComputeQueueFamilyIndex(); 
        queueCreateInfo.queueFamilyIndex = queueFamilyIndex;
        queueCreateInfo.queueCount = 1; 
        float queuePriorities = 1.0;
        queueCreateInfo.pQueuePriorities = &queuePriorities;
        VkDeviceCreateInfo deviceCreateInfo = {};
        VkPhysicalDeviceFeatures deviceFeatures = {};
        deviceCreateInfo.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO;
        deviceCreateInfo.enabledLayerCount = enabledLayers.size();
        deviceCreateInfo.ppEnabledLayerNames = enabledLayers.data();
        deviceCreateInfo.pQueueCreateInfos = &queueCreateInfo; 
        deviceCreateInfo.queueCreateInfoCount = 1;
        deviceCreateInfo.pEnabledFeatures = &deviceFeatures;
        VK_CHECK_RESULT(vkCreateDevice(physicalDevice, &deviceCreateInfo, NULL, &device)); 
        vkGetDeviceQueue(device, queueFamilyIndex, 0, &queue);
    }

    uint32_t findMemoryType(uint32_t memoryTypeBits, VkMemoryPropertyFlags properties) {
        VkPhysicalDeviceMemoryProperties memoryProperties;
        vkGetPhysicalDeviceMemoryProperties(physicalDevice, &memoryProperties);
        // See the documentation of VkPhysicalDeviceMemoryProperties for a detailed description of this search 
        for (uint32_t i = 0; i < memoryProperties.memoryTypeCount; ++i) {
            if ((memoryTypeBits & (1 << i)) &&
                ((memoryProperties.memoryTypes[i].propertyFlags & properties) == properties))
                return i;
        }
        return -1;
    }

    void createBuffers() {
        int bufferIndex = 0;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = TEST_DATA;
        bufferInfos[bufferIndex].size = testMemorySize; // testing buffer 
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = RESULTS;
        bufferInfos[bufferIndex].size = {{ numOutputs }}; // output buffer
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = SHUFFLE_IDS;
        bufferInfos[bufferIndex].size = numWorkgroups * workgroupSize; // thread shuffle buffer
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = BARRIER;
        bufferInfos[bufferIndex].size = 1; // barrier buffer
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = SCRATCHPAD;
        bufferInfos[bufferIndex].size = scratchMemorySize;
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = SCRATCH_LOCATIONS;
        bufferInfos[bufferIndex].size = numWorkgroups;
        bufferIndex++;
        bufferInfos.push_back(BufferInfo());
        bufferInfos[bufferIndex].bufferType = POD_ARGS;
        bufferInfos[bufferIndex].size = 2 + numMemLocations;
        uint32_t requiredBufferSize = 0;
	    int i = 0;
        for (BufferInfo info : bufferInfos) {
          VkBufferCreateInfo bufferCreateInfo = {};
          bufferCreateInfo.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO;
          bufferCreateInfo.size = info.size * sizeof(uint32_t); // buffer size in bytes. 
          bufferCreateInfo.usage = VK_BUFFER_USAGE_STORAGE_BUFFER_BIT; // buffer is used as a storage buffer.
          bufferCreateInfo.sharingMode = VK_SHARING_MODE_EXCLUSIVE; // buffer is exclusive to a single queue family at a time. 
          VK_CHECK_RESULT(vkCreateBuffer(device, &bufferCreateInfo, NULL, &info.buffer)); // create buffer.
          VkMemoryRequirements memoryRequirements;
          vkGetBufferMemoryRequirements(device, info.buffer, &memoryRequirements);
          info.requiredSize = memoryRequirements.size;
          info.memOffset = requiredBufferSize;
          requiredBufferSize += memoryRequirements.size;
	      bufferInfos[i] = info;
	      i++;
        }
        VkDeviceSize memorySize = requiredBufferSize;
        VkMemoryAllocateInfo allocateInfo = {};
        allocateInfo.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO;
        allocateInfo.allocationSize = memorySize;
        VkMemoryRequirements memoryRequirements;
        vkGetBufferMemoryRequirements(device, bufferInfos[0].buffer, &memoryRequirements);
        allocateInfo.memoryTypeIndex = findMemoryType(
            memoryRequirements.memoryTypeBits, VK_MEMORY_PROPERTY_HOST_COHERENT_BIT | VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT);
        VK_CHECK_RESULT(vkAllocateMemory(device, &allocateInfo, NULL, &bufferMemory));
        VkDeviceSize memoryOffset = 0;
        i = 0;
        for (BufferInfo info : bufferInfos) {
          VK_CHECK_RESULT(vkBindBufferMemory(device, info.buffer, bufferMemory, memoryOffset));
          memoryOffset += info.requiredSize;
        }
    }

    void createDescriptorSetLayout() {
        VkDescriptorSetLayoutBinding descriptorSetLayoutBindings[bufferInfos.size()];
        for (int i = 0; i < bufferInfos.size(); i++) {
          VkDescriptorSetLayoutBinding descriptorSetLayoutBinding = {};
          descriptorSetLayoutBinding.binding = i;
          descriptorSetLayoutBinding.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
          descriptorSetLayoutBinding.descriptorCount = 1;
          descriptorSetLayoutBinding.stageFlags = VK_SHADER_STAGE_COMPUTE_BIT;
          descriptorSetLayoutBindings[i] = descriptorSetLayoutBinding;
        }
        VkDescriptorSetLayoutCreateInfo descriptorSetLayoutCreateInfo = {};
        descriptorSetLayoutCreateInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO;
        descriptorSetLayoutCreateInfo.bindingCount = bufferInfos.size();
        descriptorSetLayoutCreateInfo.pBindings = descriptorSetLayoutBindings; 
        VK_CHECK_RESULT(vkCreateDescriptorSetLayout(device, &descriptorSetLayoutCreateInfo, NULL, &descriptorSetLayout));
    }

    void createDescriptorSet() {
        VkDescriptorPoolSize descriptorPoolSize = {};
        descriptorPoolSize.type = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER;
        descriptorPoolSize.descriptorCount = bufferInfos.size();

        VkDescriptorPoolCreateInfo descriptorPoolCreateInfo = {};
        descriptorPoolCreateInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_POOL_CREATE_INFO;
        descriptorPoolCreateInfo.maxSets = 1; // we only need to allocate one descriptor set from the pool.
        descriptorPoolCreateInfo.poolSizeCount = 1;
        descriptorPoolCreateInfo.pPoolSizes = &descriptorPoolSize;
        VK_CHECK_RESULT(vkCreateDescriptorPool(device, &descriptorPoolCreateInfo, NULL, &descriptorPool));

        VkDescriptorSetAllocateInfo descriptorSetAllocateInfo = {};
        descriptorSetAllocateInfo.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_ALLOCATE_INFO; 
        descriptorSetAllocateInfo.descriptorPool = descriptorPool; // pool to allocate from.
        descriptorSetAllocateInfo.descriptorSetCount = 1; // allocate a single descriptor set.
        descriptorSetAllocateInfo.pSetLayouts = &descriptorSetLayout;
        VK_CHECK_RESULT(vkAllocateDescriptorSets(device, &descriptorSetAllocateInfo, &descriptorSet));

        VkDescriptorBufferInfo descriptorBufferInfos[bufferInfos.size()];
        VkWriteDescriptorSet writeDescriptorSets[bufferInfos.size()];
        for (int i = 0; i < bufferInfos.size(); i++) {
          VkDescriptorBufferInfo descriptorBufferInfo = {};
          descriptorBufferInfo.buffer = bufferInfos[i].buffer;
          descriptorBufferInfo.offset = 0;
          descriptorBufferInfo.range = VK_WHOLE_SIZE;
          descriptorBufferInfos[i] = descriptorBufferInfo;
          VkWriteDescriptorSet writeDescriptorSet = {};
          writeDescriptorSet.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET;
          writeDescriptorSet.dstSet = descriptorSet; 
          writeDescriptorSet.dstBinding = i; 
          writeDescriptorSet.descriptorCount = 1;
          writeDescriptorSet.descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_BUFFER; 
          writeDescriptorSet.pBufferInfo = &descriptorBufferInfos[i];
          writeDescriptorSets[i] = writeDescriptorSet;
        }
        vkUpdateDescriptorSets(device, bufferInfos.size(), writeDescriptorSets, 0, NULL);
    }

    void createComputePipeline() {
        uint32_t filelength;
        VkShaderModuleCreateInfo createInfo = {};
        createInfo.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO;
        createInfo.pCode = shader;
        createInfo.codeSize = sizeof(shader);
        VK_CHECK_RESULT(vkCreateShaderModule(device, &createInfo, NULL, &computeShaderModule));
        VkPipelineShaderStageCreateInfo shaderStageCreateInfo = {};
        shaderStageCreateInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO;
        shaderStageCreateInfo.stage = VK_SHADER_STAGE_COMPUTE_BIT;
        shaderStageCreateInfo.module = computeShaderModule;
        shaderStageCreateInfo.pName = "litmus_test";

        VkPipelineLayoutCreateInfo pipelineLayoutCreateInfo = {};
        pipelineLayoutCreateInfo.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO;
        pipelineLayoutCreateInfo.setLayoutCount = 1;
        pipelineLayoutCreateInfo.pSetLayouts = &descriptorSetLayout; 
        VK_CHECK_RESULT(vkCreatePipelineLayout(device, &pipelineLayoutCreateInfo, NULL, &pipelineLayout));
        VkComputePipelineCreateInfo pipelineCreateInfo = {};
        pipelineCreateInfo.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO;
        pipelineCreateInfo.stage = shaderStageCreateInfo;
        pipelineCreateInfo.layout = pipelineLayout;
        VK_CHECK_RESULT(vkCreateComputePipelines(
            device, VK_NULL_HANDLE,
            1, &pipelineCreateInfo,
            NULL, &pipeline));
   }

    void createCommandBuffer() {
        VkCommandPoolCreateInfo commandPoolCreateInfo = {};
        commandPoolCreateInfo.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO;
        commandPoolCreateInfo.flags = 0;
        commandPoolCreateInfo.queueFamilyIndex = queueFamilyIndex;
        VK_CHECK_RESULT(vkCreateCommandPool(device, &commandPoolCreateInfo, NULL, &commandPool));

        VkCommandBufferAllocateInfo commandBufferAllocateInfo = {};
        commandBufferAllocateInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO;
        commandBufferAllocateInfo.commandPool = commandPool;
        commandBufferAllocateInfo.level = VK_COMMAND_BUFFER_LEVEL_PRIMARY;
        commandBufferAllocateInfo.commandBufferCount = 1;
        VK_CHECK_RESULT(vkAllocateCommandBuffers(device, &commandBufferAllocateInfo, &commandBuffer));

        VkCommandBufferBeginInfo beginInfo = {};
        beginInfo.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO;
        beginInfo.flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT; // the buffer is only submitted and used once in this application.
        VK_CHECK_RESULT(vkBeginCommandBuffer(commandBuffer, &beginInfo)); // start recording commands.

        vkCmdBindPipeline(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, pipeline);
        vkCmdBindDescriptorSets(commandBuffer, VK_PIPELINE_BIND_POINT_COMPUTE, pipelineLayout, 0, 1, &descriptorSet, 0, NULL);
        vkCmdDispatch(commandBuffer, numWorkgroups, 1, 1);
        VK_CHECK_RESULT(vkEndCommandBuffer(commandBuffer)); // end recording commands.
    }

    void runCommandBuffer() {
        VkSubmitInfo submitInfo = {};
        submitInfo.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;
        submitInfo.commandBufferCount = 1;
        submitInfo.pCommandBuffers = &commandBuffer;
        VkFence fence;
        VkFenceCreateInfo fenceCreateInfo = {};
        fenceCreateInfo.sType = VK_STRUCTURE_TYPE_FENCE_CREATE_INFO;
        fenceCreateInfo.flags = 0;
        VK_CHECK_RESULT(vkCreateFence(device, &fenceCreateInfo, NULL, &fence));
        VK_CHECK_RESULT(vkQueueSubmit(queue, 1, &submitInfo, fence));
        VK_CHECK_RESULT(vkWaitForFences(device, 1, &fence, VK_TRUE, 100000000000));
        vkDestroyFence(device, fence, NULL);
    }

    void cleanup() {
        if (enableValidationLayers) {
            auto func = (PFN_vkDestroyDebugReportCallbackEXT)vkGetInstanceProcAddr(instance, "vkDestroyDebugReportCallbackEXT");
            if (func == nullptr) {
                throw runtime_error("Could not load vkDestroyDebugReportCallbackEXT");
            }
            func(instance, debugReportCallback, NULL);
        }

        vkFreeMemory(device, bufferMemory, NULL);
	    for (BufferInfo info : bufferInfos) 
          vkDestroyBuffer(device, info.buffer, NULL);	
        vkDestroyShaderModule(device, computeShaderModule, NULL);
        vkDestroyDescriptorPool(device, descriptorPool, NULL);
        vkDestroyDescriptorSetLayout(device, descriptorSetLayout, NULL);
        vkDestroyPipelineLayout(device, pipelineLayout, NULL);
        vkDestroyPipeline(device, pipeline, NULL);
        vkDestroyCommandPool(device, commandPool, NULL);	
        vkDestroyDevice(device, NULL);
        vkDestroyInstance(instance, NULL);		
    }
};

int main(int argc, char* argv[]) {
    ComputeApplication app;
    try {
        app.run();
        printf("weak behavior: %d\n", weakBehavior);
        printf("non weak behavior: %d\n", nonWeakBehavior);
    }
    catch (const runtime_error& e) {
        printf("%s\n", e.what());
        return EXIT_FAILURE;
    }
    
    return EXIT_SUCCESS;
}
