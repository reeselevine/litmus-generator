LOCAL_PATH := $(call my-dir)

include $(CLEAR_VARS)

LOCAL_MODULE    := runner
LOCAL_C_INCLUDES := ../easyvk/src
LOCAL_SRC_FILES := runner.cpp ../easyvk/src/easyvk.cpp
LOCAL_LDLIBS    += -lvulkan -llog

include $(BUILD_EXECUTABLE)
