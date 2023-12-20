#!/bin/bash

# build the Android binary
ndk-build NDK_PROJECT_PATH=./ NDK_APPLICATION_MK=./Application.mk APP_BUILD_SCRIPT=./Android.mk


# move files to android device
adb push shaders /data/local/tmp/test-runner/shaders
adb push libs/armeabi-v7a/runner /data/local/tmp/test-runner/
adb push tune.sh /data/local/tmp/test-runner/
