#!/bin/sh
# Oink configuration — edit DASHBOARD_URL before first use.
#
# For this repository the published image is:
#   https://Alldred.github.io/oink/dashboard.png
#
# If you forked the project, replace Alldred with your GitHub username.

# Required: public URL of the generated dashboard PNG
DASHBOARD_URL="https://Alldred.github.io/oink/dashboard.png"

# How often the background loop refreshes (seconds). Default: 30 minutes.
REFRESH_SECONDS=1800

# How often to force a full e-ink refresh (reduces ghosting). Counted in
# successful updates. Set to 1 to full-refresh every time.
FULL_REFRESH_EVERY=6

# Optional IANA-style note only — the clock timezone is set in GitHub Actions /
# generate_dashboard.py, not on the Kindle.
# DISPLAY_TIMEZONE=Europe/London
