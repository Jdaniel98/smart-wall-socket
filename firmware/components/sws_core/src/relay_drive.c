#include "sws/relay_drive.h"

void relay_drive_init(relay_drive_t *r)
{
    r->closed = false;
    r->energised_at = 0;
}

uint16_t relay_drive_duty(relay_drive_t *r, const relay_drive_cfg_t *cfg, bool want_closed,
                          sws_ms_t now)
{
    if (!want_closed) {
        r->closed = false;
        return 0;
    }
    if (!r->closed) {
        r->closed = true;
        r->energised_at = now;
    }
    if (now - r->energised_at < cfg->pull_in_ms) {
        return 1000;
    }
    return cfg->hold_permille > 1000 ? 1000 : cfg->hold_permille;
}

uint32_t relay_zc_delay_us(uint32_t operate_us, uint32_t half_period_us)
{
    if (half_period_us == 0) {
        return 0;
    }
    const uint32_t rem = operate_us % half_period_us;
    return rem == 0 ? 0 : half_period_us - rem;
}
