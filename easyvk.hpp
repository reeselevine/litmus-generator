#include <vulkan/vulkan.hpp>
#include <vector>
#include <iostream>


namespace easyvk {

    class Instance {
        public:
            static auto VKAPI_ATTR debugReporter(
	            VkDebugReportFlagsEXT , VkDebugReportObjectTypeEXT, uint64_t, size_t, int32_t
	            , const char*                pLayerPrefix
	            , const char*                pMessage
	            , void*                      /*pUserData*/)-> VkBool32 {
	            std::cerr << "[Vulkan]:" << pLayerPrefix << ": " << pMessage << "\n";
	            return VK_FALSE;
            }

            Instance(bool _enableValidationLayers=false) {
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

	    std::vector<Device> devices() {
                auto physicalDevices = instance.enumeratePhysicalDevices();
	        auto devices = std::vector<Device>{};
		for (auto device : physicalDevices) {
		    devices.push_back(Device(*this, device));
		}
		return devices;
	    }

	    auto clear() {
	        if (enableValidationLayers) {
		    auto destroyFn = PFN_vkDestroyDebugReportCallbackEXT(instance.getProcAddr("vkDestroyDebugReportCallbackEXT"));
		    if (destroyFn) {
		        destroyFn(instance, debugReportCallback, nullptr);
		    }
		}
		instance.destroy();
	    }
        private:
	    bool enableValidationLayers;
            vk::Instance instance;
	    VkDebugReportCallbackEXT debugReportCallback;
    };

    class Device {
        public:
	   Device(Instance &instance, vk::PhysicalDevice _physicalDevice) {
	       physicalDevice = _physicalDevice;
               auto familyProperties = physical_device.getQueueFamilyProperties();
	       uint32_t i = 0;
	       for (auto queueFamily : familyProperties) {
		   if (queueFamily.queueCount > 0 && (queueFamily.queueFlags && vk::QueueFlagBits::eCompute)) {
		       computeFamilyId = i;; 
		       break;
		   }
		   i++;
	       }

	       auto queueCreateInfo = vk::DeviceQueueCreateInfo(vk::DeviceQueueCreateFlags(), computeFamilyId, 1, float(1.0));
	       auto deviceCreateInfo = vk::DeviceCreateInfo(vk::DeviceCreateFlags(), 1, {queueCreateInfo});
	       device = physicalDevice.createDevice(deviceCreateInfo, nullptr);
	   } 

        private:
	    Instance &_instance;
	    vk::PhysicalDevice physicalDevice;
	    vk::Device device;
	    vk::CommandPool    computePool;
	    vk::CommandBuffer  computeCommandBuffer;
	    uint32_t computeFamilyId = uint32_t(-1);
    };

}
