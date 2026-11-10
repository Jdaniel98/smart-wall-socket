/* Minimal test harness: no dependencies, works in CI and on any laptop. */
#pragma once

#include <math.h>
#include <stdio.h>
#include <string.h>

extern int g_failures;
extern int g_checks;

#define CHECK(cond)                                                                    \
    do {                                                                               \
        g_checks++;                                                                    \
        if (!(cond)) {                                                                 \
            g_failures++;                                                              \
            fprintf(stderr, "  FAIL %s:%d: %s\n", __FILE__, __LINE__, #cond);          \
        }                                                                              \
    } while (0)

#define CHECK_NEAR(a, b, tol)                                                          \
    do {                                                                               \
        g_checks++;                                                                    \
        double _a = (double)(a), _b = (double)(b);                                     \
        if (!(fabs(_a - _b) <= (tol))) {                                               \
            g_failures++;                                                              \
            fprintf(stderr, "  FAIL %s:%d: %s = %.6f, expected %.6f +- %g\n", __FILE__, \
                    __LINE__, #a, _a, _b, (double)(tol));                              \
        }                                                                              \
    } while (0)

#define RUN(fn)                                \
    do {                                       \
        int _before = g_failures;              \
        fn();                                  \
        printf("%s %s\n", g_failures == _before ? "ok  " : "FAIL", #fn); \
    } while (0)

void suite_bl0939(void);
void suite_energy(void);
void suite_protection(void);
void suite_schedule(void);
void suite_relay(void);
void suite_proto(void);
