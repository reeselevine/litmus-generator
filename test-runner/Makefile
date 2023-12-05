CXX = g++
CXXFLAGS = -std=c++17
CLSPVFLAGS = -cl-std=CL2.0 -inline-entry-points

SHADERS = $(patsubst %.cl,%.spv,$(wildcard shaders/*/*.cl))
SOURCE_DIRS = $(wildcard shaders/*)

.PHONY: clean easyvk copy_param_files

all: build easyvk runner $(SHADERS) copy_param_files tuning

build:
	mkdir -p build

clean:
	rm -r build

easyvk: ../easyvk/src/easyvk.cpp ../easyvk/src/easyvk.h
	$(CXX) $(CXXFLAGS) -I../easyvk/src -c ../easyvk/src/easyvk.cpp -o build/easyvk.o

runner: runner.cpp 
	$(CXX) $(CXXFLAGS) -I../easyvk/src build/easyvk.o runner.cpp -lvulkan -o build/runner

%.spv: %.cl
	clspv -w -cl-std=CL2.0 -inline-entry-points $< -o build/$(notdir $@)


copy_param_files:
	for src_dir in $(SOURCE_DIRS); do \
		cp $$src_dir/*.txt build; \
	done

tuning: tune.sh 
	cp $< build

