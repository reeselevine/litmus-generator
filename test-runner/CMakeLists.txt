cmake_minimum_required(VERSION 3.16)
# set the project name
project(TestRunner)

# Find Vulkan
find_package(Vulkan REQUIRED FATAL_ERROR)

# Set up external libraries
add_subdirectory(lib/easyvk)

# add the executable
add_executable(TestRunner test_runner.cpp)

# Link libraries
target_link_libraries(TestRunner easyvk)
target_link_libraries(TestRunner ${Vulkan_LIBRARIES})

# Include library headers
target_include_directories(
	TestRunner PUBLIC
	"${PROJECT_SOURCE_DIR}/lib/easyvk/include"
	${Vulkan_INCLUDE_DIRS}
)
