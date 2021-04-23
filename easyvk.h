#include <vulkan/vulkan.hpp>
#include <vector>

namespace easyvk {

	class Device;
	class Buffer;

	class Instance {
		public:
			Instance(bool _enableValidationLayers);
			std::vector<easyvk::Device> devices();
			void clear();
		private:
			bool enableValidationLayers;
			vk::Instance instance;
			VkDebugReportCallbackEXT debugReportCallback;
	};

	class Device {
		public:
			Device(Instance &_instance, vk::PhysicalDevice _physicalDevice);
			vk::Device device;
			uint32_t selectMemory(vk::Buffer buffer, vk::MemoryPropertyFlags flags);
			vk::Queue computeQueue();
			vk::CommandBuffer computeCommandBuffer;
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
		private:
			easyvk::Device &device;
			vk::DeviceMemory memory;
			uint32_t size;
			uint32_t* data;
	};

	class Program {
		public:
			Program(Device &_device, const char* filepath, std::vector<easyvk::Buffer> buffers, int numWorkgroups);
			void run();
		private:
			vk::ShaderModule shaderModule;
			easyvk::Device &device;
			vk::DescriptorSetLayout descriptorSetLayout;
			vk::DescriptorPool descriptorPool;
			vk::DescriptorSet descriptorSet;
			vk::PipelineLayout pipelineLayout;
			vk::Pipeline pipeline;
			std::array<uint32_t, 3> workgroups={0, 0, 0};
	};

}
