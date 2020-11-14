// Your First C++ Program

#include <iostream>
#include <array>

int main() {
    int *a;
    int *b;
    int *c;
    std::array<int*,3> arr = {a, b, c};
    for (int i = 0; i < 3; i++) {
        int x = i;
        arr[i] = &x;
    }
    for (int i = 0; i < 3; i++) {
        std::cout << *arr[i] << " ";
    }
    return 0;
}
