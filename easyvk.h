#include <vulkan/vulkan.hpp>
#include <vector>

namespace easyvk {

	class Device;
	class Buffer;

	class Instance {
		public:
			Instance(bool _enableValidationLayers);
			std::vector<easyvk::Device> devices();
			void teardown();
		private:
			bool enableValidationLayers;
			vk::Instance instance;
			VkDebugReportCallbackEXT debugReportCallback;
	};

	class Device {
		public:
			Device(Instance &_instance, vk::PhysicalDevice _physicalDevice);
			vk::Device device;
			vk::PhysicalDeviceProperties properties();
			uint32_t selectMemory(vk::Buffer buffer, vk::MemoryPropertyFlags flags);
			vk::Queue computeQueue();
			vk::CommandBuffer computeCommandBuffer;
			void teardown();
		private:
			Instance &instance;
			vk::PhysicalDevice physicalDevice;
			vk::CommandPool computePool;
			uint32_t computeFamilyId = uint32_t(-1);
	};

	class Buffer {
		public:
			Buffer(Device &device, uint32_t size);
			vk::Buffer buffer;

			void store(size_t i, uint32_t value) {
				*(data + i) = value;
			}

			uint32_t load(size_t i) {
				return *(data + i);
			}

			void teardown();
		private:
			easyvk::Device &device;
			vk::DeviceMemory memory;
			uint32_t size;
			uint32_t* data;
	};

	class Program {
		public:
			Program(Device &_device, const char* filepath, std::vector<easyvk::Buffer> buffers);
			void prepare();
			void run();
			void setWorkgroups(uint32_t _numWorkgroups);
			void setWorkgroupSize(uint32_t _workgroupSize);
			void teardown();
		private:
			std::vector<easyvk::Buffer> buffers;
			vk::ShaderModule shaderModule;
			easyvk::Device &device;
			vk::DescriptorSetLayout descriptorSetLayout;
			vk::DescriptorPool descriptorPool;
			vk::DescriptorSet descriptorSet;
			vk::PipelineLayout pipelineLayout;
			vk::Pipeline pipeline;
			uint32_t numWorkgroups;
			uint32_t workgroupSize;
	};

}
