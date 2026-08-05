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

# Draw local HH:MM in the upper-left after every paint (eips text overlay).
# Set to 0 to disable. Optional CLOCK_COL / CLOCK_ROW override position.
CLOCK_OVERLAY=1
