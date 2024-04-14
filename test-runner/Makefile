CXX = g++
CXXFLAGS = -std=c++17
CLSPVFLAGS = -cl-std=CL2.0 -inline-entry-points

.PHONY: clean easyvk runner

all: easyvk runner

clean:
	rm easyvk.o
	rm runner

easyvk: easyvk/src/easyvk.cpp easyvk/src/easyvk.h
	$(CXX) $(CXXFLAGS) -Ieasyvk/src -c easyvk/src/easyvk.cpp -o easyvk.o

runner: runner.cpp 
	$(CXX) $(CXXFLAGS) -Ieasyvk/src easyvk.o runner.cpp -lvulkan -o runner

%.spv: %.cl
	clspv -cl-std=CL2.0 -inline-entry-points $< -o $@
