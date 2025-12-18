# Troubleshooting notes

## "Flashing is disabled (policy.flash_enabled=false)."
Expected until policy enables flashing. /api/flash should refuse with HTTP 403.

## JSONDecodeError loop
This happens when a script does json.load(...) on empty input.
Most common causes:
- curl failed (connection refused, timeout, etc) and wrote nothing
- service restarted mid-request and the client saved an empty file
Fix patterns:
- use: curl -fsS (fail on non-200 and no HTML junk)
- verify file non-empty before python parses:
  - test -s /tmp/file.json
- in python, catch JSONDecodeError and print body for debugging

## Service restarts
jr-golden-sd.service restarts show up as gunicorn workers receiving SIGTERM.
If this coincides with client polling loops, you can get empty responses.
