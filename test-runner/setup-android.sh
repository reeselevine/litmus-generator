#!/bin/bash

# build the spv files
make

# build the Android binary
ndk-build NDK_PROJECT_PATH=./ NDK_APPLICATION_MK=./Application.mk APP_BUILD_SCRIPT=./Android.mk


# move files to android device
adb push build /data/local/tmp/time-bounds
adb push libs/armeabi-v7a/runner /data/local/tmp/time-bounds/
adb push android-tune.sh /data/local/tmp/time-bounds/
