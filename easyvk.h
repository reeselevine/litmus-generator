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
		private:
			Instance &instance;
			vk::PhysicalDevice physicalDevice;
			vk::CommandPool computePool;
			vk::CommandBuffer computeCommandBuffer;
			uint32_t computeFamilyId = uint32_t(-1);
	};

	class Buffer {
		public:
			Buffer(Device &device, uint32_t size);
		private:
			easyvk::Device &device;
			vk::Buffer buffer;
			vk::DeviceMemory memory;
			uint32_t size;
			uint32_t* data;
	};
}
