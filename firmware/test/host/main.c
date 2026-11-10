#include "test.h"

int g_failures = 0;
int g_checks = 0;

int main(void)
{
    suite_bl0939();
    suite_energy();
    suite_protection();
    suite_schedule();
    suite_relay();
    suite_proto();
    printf("\n%d checks, %d failures\n", g_checks, g_failures);
    return g_failures == 0 ? 0 : 1;
}
