easyvk : easyvk.hpp
	g++ -DNDEBUG -g -I/shared/vuh-sources/include -std=gnu++14 -c -o easyvk.o easyvk.hpp -lvulkan
	ar rcs lib/libeasyvk.a easyvk.o
