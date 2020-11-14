#include <stdio.h>
#include <stdlib.h>

void fibonacci_sequence(int n) {
    if (n < 0) {
        printf("Invalid argument!\n");
    }
    unsigned int cur, prev;
    prev = 0;
    cur = 0;
    while (n > 0) {
        printf("%i\n", cur);
        if (cur == 0) {
            cur = 1;
        } else {
            int temp;
            temp = prev;
            prev = cur;
            cur = cur + temp;
        }
        n--;
    }
}

int main(int argc, char *argv[]) {
    printf("hello %s, you are %d years old", "Reese",25);
    if (argc != 2) {
        printf("Wrong number of arguments included!\n");
        return 1;
    } else {
        int n;
        n = atoi(argv[1]);
        fibonacci_sequence(n);
    }
    return 0;
}
