#include <vulkan/vulkan.hpp>
#include <vector>
#include <array>
#include <iostream>
#include "easyvk.h"
#include <fstream>

namespace easyvk {

	static auto VKAPI_ATTR debugReporter(
	            VkDebugReportFlagsEXT , VkDebugReportObjectTypeEXT, uint64_t, size_t, int32_t
	            , const char*                pLayerPrefix
	            , const char*                pMessage
	            , void*                      /*pUserData*/)-> VkBool32 {
	            std::cerr << "[Vulkan]:" << pLayerPrefix << ": " << pMessage << "\n";
	            return VK_FALSE;
            }

	Instance::Instance(bool _enableValidationLayers=false) {
		enableValidationLayers = _enableValidationLayers;
                std::vector<const char *> enabledLayers;
                std::vector<const char *> enabledExtensions;
                if (enableValidationLayers) {
                    enabledLayers.push_back("VK_LAYER_LUNARG_standard_validation");
                    enabledExtensions.push_back(VK_EXT_DEBUG_REPORT_EXTENSION_NAME);
                }
                vk::ApplicationInfo appInfo("Litmus Tester", 0, "LSD Lab", 0, VK_API_VERSION_1_0);
                vk::InstanceCreateInfo createInfo(vk::InstanceCreateFlags(), &appInfo, enabledLayers.size(), enabledLayers.data(), enabledExtensions.size(), enabledExtensions.data());
                instance = vk::createInstance(createInfo);
                if (enableValidationLayers) {
		    auto debugCreateInfo = VkDebugReportCallbackCreateInfoEXT{};
		    debugCreateInfo.sType = VK_STRUCTURE_TYPE_DEBUG_REPORT_CALLBACK_CREATE_INFO_EXT;
		    debugCreateInfo.flags = VK_DEBUG_REPORT_ERROR_BIT_EXT | VK_DEBUG_REPORT_WARNING_BIT_EXT
		                   | VK_DEBUG_REPORT_PERFORMANCE_WARNING_BIT_EXT;
		    debugCreateInfo.pfnCallback = debugReporter;
                    auto createFN = PFN_vkCreateDebugReportCallbackEXT(instance.getProcAddr("vkCreateDebugReportCallbackEXT"));
                    if(createFN) {
		        createFN(instance, &debugCreateInfo, nullptr, &debugReportCallback);
		    }
                }
            }

	std::vector<easyvk::Device> Instance::devices() {
                auto physicalDevices = instance.enumeratePhysicalDevices();
	        auto devices = std::vector<easyvk::Device>{};
		for (auto device : physicalDevices) {
		    devices.push_back(easyvk::Device(*this, device));
		}
		return devices;
	    }

	void Instance::teardown() {
	        if (enableValidationLayers) {
		    auto destroyFn = PFN_vkDestroyDebugReportCallbackEXT(instance.getProcAddr("vkDestroyDebugReportCallbackEXT"));
		    if (destroyFn) {
		        destroyFn(instance, debugReportCallback, nullptr);
		    }
		}
		instance.destroy();
	}

	uint32_t getComputeFamilyId(vk::PhysicalDevice physicalDevice) {
		auto familyProperties = physicalDevice.getQueueFamilyProperties();
		uint32_t i = 0;
		uint32_t computeFamilyId = -1;
		for (auto queueFamily : familyProperties) {
			if (queueFamily.queueCount > 0 && (queueFamily.queueFlags & vk::QueueFlagBits::eCompute)) {
				computeFamilyId = i;; 
				break;
			}
			i++;
		}
		return computeFamilyId;
	}

	Device::Device(easyvk::Instance &_instance, vk::PhysicalDevice _physicalDevice) : 
		instance(_instance),
		physicalDevice(_physicalDevice),
		computeFamilyId(getComputeFamilyId(_physicalDevice)) {
		auto priority = float(1.0);
		auto queues = std::array<vk::DeviceQueueCreateInfo, 1>{};
		queues[0] = vk::DeviceQueueCreateInfo(vk::DeviceQueueCreateFlags(), computeFamilyId, 1, &priority);
		auto deviceCreateInfo = vk::DeviceCreateInfo(vk::DeviceCreateFlags(), 1, queues.data());
		device = physicalDevice.createDevice(deviceCreateInfo, nullptr);
		computePool = device.createCommandPool({vk::CommandPoolCreateFlagBits::eResetCommandBuffer, computeFamilyId});
		auto commandBufferAI = vk::CommandBufferAllocateInfo(computePool, vk::CommandBufferLevel::ePrimary, 1);
		computeCommandBuffer = device.allocateCommandBuffers(commandBufferAI)[0];
	}

	vk::PhysicalDeviceProperties Device::properties() {
		return physicalDevice.getProperties();
	}

	uint32_t Device::selectMemory(vk::Buffer buffer, vk::MemoryPropertyFlags flags) {
		auto memProperties = physicalDevice.getMemoryProperties();
		auto memoryReqs = device.getBufferMemoryRequirements(buffer);
		for(uint32_t i = 0; i < memProperties.memoryTypeCount; ++i){
			if( (memoryReqs.memoryTypeBits & (1u << i))
			    && ((flags & memProperties.memoryTypes[i].propertyFlags) == flags))
			{
				return i;
			}
		}
		return uint32_t(-1);
	}

	vk::Queue Device::computeQueue() {
		return device.getQueue(computeFamilyId, 0);
	}

	void Device::teardown() {
		device.destroyCommandPool(computePool);
		device.destroy();
	}

	Buffer::Buffer(easyvk::Device &_device, uint32_t size) :
		device(_device),
		buffer(device.device.createBuffer({ {}, size * sizeof(uint32_t), vk::BufferUsageFlagBits::eStorageBuffer})) {
		auto memId = device.selectMemory(buffer, vk::MemoryPropertyFlagBits::eHostVisible);
		memory = device.device.allocateMemory({device.device.getBufferMemoryRequirements(buffer).size, memId});
		device.device.bindBufferMemory(buffer, memory, 0);
		data = static_cast<uint32_t*>(device.device.mapMemory(memory, 0, VK_WHOLE_SIZE));
	}

	void Buffer::teardown() {
		device.device.unmapMemory(memory);
		device.device.freeMemory(memory);
		device.device.destroyBuffer(buffer);
	}

	std::vector<uint32_t> read_spirv(const char* filename) {
		auto fin = std::ifstream(filename, std::ios::binary | std::ios::ate);
		if(!fin.is_open()){
			throw std::runtime_error(std::string("failed opening file ") + filename + " for reading");
		}
		const auto stream_size = unsigned(fin.tellg());
		fin.seekg(0);

		auto ret = std::vector<std::uint32_t>((stream_size + 3)/4, 0);
		std::copy( std::istreambuf_iterator<char>(fin), std::istreambuf_iterator<char>()
	         	  , reinterpret_cast<char*>(ret.data()));
		return ret;
	}

	vk::ShaderModule initShaderModule(easyvk::Device& device, const char* filepath) {
		std::vector<uint32_t> code = read_spirv(filepath);
		return device.device.createShaderModule({ {}, code.size() * sizeof(uint32_t), code.data()});
	}

	vk::DescriptorSetLayout createDescriptorSetLayout(easyvk::Device &device, uint32_t size) {
		std::vector<vk::DescriptorSetLayoutBinding> layouts;
		for (int i = 0; i < size; i++) {
			layouts.push_back(vk::DescriptorSetLayoutBinding(i, vk::DescriptorType::eStorageBuffer, 1, vk::ShaderStageFlagBits::eCompute));
		}
		auto createInfo = vk::DescriptorSetLayoutCreateInfo(vk::DescriptorSetLayoutCreateFlags(), uint32_t(size), layouts.data());
		return device.device.createDescriptorSetLayout(createInfo);
	}

	std::vector<vk::WriteDescriptorSet> writeSets(vk::DescriptorSet& descriptorSet, std::vector<easyvk::Buffer> buffers) {
		std::vector<vk::WriteDescriptorSet> writeDescriptorSets;
		std::vector<vk::DescriptorBufferInfo> bufferInfos;
		for (int i = 0; i < buffers.size(); i++) {
			bufferInfos.push_back(vk::DescriptorBufferInfo(buffers[i].buffer, 0, VK_WHOLE_SIZE));
			writeDescriptorSets.push_back(vk::WriteDescriptorSet(descriptorSet, i, 0, 1, vk::DescriptorType::eStorageBuffer, nullptr, &bufferInfos[i], nullptr));
		}
		return writeDescriptorSets;

	}

	void Program::prepare() {
		vk::SpecializationMapEntry specMap[1] = {vk::SpecializationMapEntry(0, 0, sizeof(uint32_t))};
		uint32_t specMapContent[1] = {workgroupSize};
		auto specInfo = vk::SpecializationInfo(1, specMap, sizeof(uint32_t), specMapContent);
		auto stageCI = vk::PipelineShaderStageCreateInfo(vk::PipelineShaderStageCreateFlags(), vk::ShaderStageFlagBits::eCompute, shaderModule, "litmus_test", &specInfo);
		auto pipelineCI = vk::ComputePipelineCreateInfo({}, stageCI, pipelineLayout);
		pipeline = device.device.createComputePipeline(nullptr, pipelineCI, nullptr);
		device.computeCommandBuffer.begin(vk::CommandBufferBeginInfo());
		device.computeCommandBuffer.bindPipeline(vk::PipelineBindPoint::eCompute, pipeline);
		device.computeCommandBuffer.bindDescriptorSets(vk::PipelineBindPoint::eCompute, pipelineLayout, 0, {descriptorSet}, {});
		device.computeCommandBuffer.dispatch(numWorkgroups, 1, 1);
		device.computeCommandBuffer.end();
	}

	void Program::run() {
		auto submitInfo = vk::SubmitInfo(0, nullptr, nullptr, 1, &device.computeCommandBuffer);
		auto queue = device.computeQueue();
		queue.submit({submitInfo}, nullptr);
		queue.waitIdle();
	}

	void Program::setWorkgroups(uint32_t _numWorkgroups) {
		numWorkgroups = _numWorkgroups;
	}

	void Program::setWorkgroupSize(uint32_t _workgroupSize) {
		workgroupSize = _workgroupSize;
	}

	Program::Program(easyvk::Device &_device, const char* filepath, std::vector<easyvk::Buffer> _buffers) :
		device(_device),
	        shaderModule(initShaderModule(_device, filepath)),
		buffers(_buffers),
		descriptorSetLayout(createDescriptorSetLayout(_device, buffers.size())) {
			vk::PipelineLayoutCreateInfo createInfo(vk::PipelineLayoutCreateFlags(), 1, &descriptorSetLayout);
			pipelineLayout = device.device.createPipelineLayout(createInfo);
			auto poolSize = vk::DescriptorPoolSize(vk::DescriptorType::eStorageBuffer, buffers.size());
			auto descriptorSizes = std::array<vk::DescriptorPoolSize, 1>({poolSize});
			descriptorPool = device.device.createDescriptorPool({vk::DescriptorPoolCreateFlags(), 1, uint32_t(descriptorSizes.size()), descriptorSizes.data()});
			descriptorSet = device.device.allocateDescriptorSets({descriptorPool, 1, &descriptorSetLayout})[0];
			device.device.updateDescriptorSets(writeSets(descriptorSet, buffers), {});
	}

	void Program::teardown() {
		device.device.destroyShaderModule(shaderModule);
		device.device.destroyDescriptorPool(descriptorPool);
		device.device.destroyDescriptorSetLayout(descriptorSetLayout);
		device.device.destroyPipelineLayout(pipelineLayout);
		device.device.destroyPipeline(pipeline);
	}
}
