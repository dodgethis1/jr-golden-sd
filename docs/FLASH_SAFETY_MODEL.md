# Flash safety gates (how we avoid nuking the wrong disk)

Hard gates in app/app.py:
1) Must be in SD mode: safety_state().can_flash_here
2) Root disk is always blocked (eligible_targets excludes it)
3) Flashing disabled by default: policy.flash_enabled=false
4) Two-phase confirmation:
   - /api/arm requires:
     - target is eligible
     - confirm_target == target
     - word matches policy.write_word (default ERASE)
     - optional serial suffix check
   - /api/flash requires:
     - policy.flash_enabled=true
     - unexpired ARM token matches target (+ os_id if provided)
     - optional serial suffix check
     - OS image must already be cached
5) One-shot: /api/flash disarms immediately before running the write job.

Operational rule:
- We keep flash_enabled=false until we are staring at the correct target disk in eligible_targets
  and we explicitly decide to permit writes.
