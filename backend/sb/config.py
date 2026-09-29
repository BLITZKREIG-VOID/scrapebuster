import os

# UPSTREAM_ORIGIN selects the public CampusCart deployment. SB_ORIGIN_URL remains
# an explicit local-origin override for the existing ExampleCorp demo and tests.
SB_ORIGIN_URL = (
    os.getenv("UPSTREAM_ORIGIN")
    or os.getenv("SB_ORIGIN_URL")
    or "https://campuscart-c73de.web.app"
)
