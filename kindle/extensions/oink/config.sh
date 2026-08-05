#!/bin/sh
# Oink configuration — edit DASHBOARD_URL before first use.
#
# For this repository the published image is:
#   https://Alldred.github.io/oink/dashboard.png
#
# If you forked the project, replace Alldred with your GitHub username.

# Required: public URL of the generated dashboard PNG
DASHBOARD_URL="https://Alldred.github.io/oink/dashboard.png"

# How often to download from Pages (seconds). Poll faster than the ~30min
# Actions publish so a missed/delayed GH run does not leave a long gap.
# Default: 5 minutes.
REFRESH_SECONDS=300

# How often to force a full e-ink refresh (reduces ghosting). Counted in
# successful *new* downloads. Set to 1 to full-refresh every time.
FULL_REFRESH_EVERY=12

# Stop the Kindle framework while Oink runs so Home cannot cover the image.
# Stop Oink starts it again. Set to 0 to try a lighter pillow/mesquite freeze.
STOP_FRAMEWORK=1

# Re-paint the cached PNG this often (seconds) between downloads.
REPAINT_SECONDS=60

# Quit Oink when the Kindle enters USB drive / mass-storage mode (so the Mac
# can mount the disk and the framework can come back). Does NOT quit on a
# plain wall charger — always-on USB power is fine. Set to 0 to disable.
QUIT_ON_USB=1

# Draw local HH:MM top-right after every paint (eips text overlay), aligned
# with the PNG date header. Set to 0 to disable. Leave CLOCK_COL unset for
# auto right-edge placement. CLOCK_ROW=1 matches the header band (0 is flush top).
CLOCK_OVERLAY=1
CLOCK_ROW=1
