#include <stdio.h>

int main(void) {
    int seed = 41;
    int observed = seed + 1;
    printf("qps-triage-docker-lldb-probe observed=%d\n", observed);
    return observed == 42 ? 0 : 1;
}
