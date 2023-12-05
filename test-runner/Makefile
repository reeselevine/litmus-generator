CXX = g++
CXXFLAGS = -std=c++17

.PHONY: clean easyvk 

all: easyvk runner

clean:
	rm easyvk.o
	rm runner

easyvk: easyvk/src/easyvk.cpp easyvk/src/easyvk.h
	$(CXX) $(CXXFLAGS) -Ieasyvk/src -c easyvk/src/easyvk.cpp -o easyvk.o

runner: runner.cpp 
	$(CXX) $(CXXFLAGS) -Ieasyvk/src easyvk.o runner.cpp -lvulkan -o runner

