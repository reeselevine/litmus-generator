#include <vulkan/vulkan.hpp>
#include <vector>

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

            Instance(bool enableValidationLayers=false) {
                std::vector<const char *> enabledLayers;
                std::vector<const char *> enabledExtensions;
                if (enableValidationLayers) {
                    enabledLayers.push_back("VK_LAYER_LUNARG_standard_validation");
                    enabledExtensions.push_back(VK_EXT_DEBUG_REPORT_EXTENSION_NAME);
                }
                vk::ApplicationInfo appInfo("Litmus Tester", 0, "LSD Lab", 0, VK_API_VERSION_1_0);
                vk::InstanceCreateInfo createInfo(vk::InstanceCreateFlags(), &appInfo, enabledLayers.size(), enabledLayers.data(), enabledExtensions.size(), enabledExtensions.data());
                instance(vk::createInstance(createInfo));
                if (enableValidationLayers) {
                    vk::DebugReportCallbackCreateInfoEXT debugCreateInfo(VK_DEBUG_REPORT_ERROR_BIT_EXT | VK_DEBUG_REPORT_WARNING_BIT_EXT | VK_DEBUG_REPORT_PERFORMANCE_WARNING_BIT_EXT, &debugReporter);
                    auto createFN = PFN_vkCreateDebugReportCallbackEXT(instance.getProcAddr("vkCreateDebugReportCallbackEXT"));
                    if(createFN) {
			            createFN(instance, &createInfo, nullptr, &debugReportCallback);
		            }
                }
            }
        private:
            vk::Instance instance;
            vk::DebugReportCallbackEXT debugReportCallback;

    }


}

        
