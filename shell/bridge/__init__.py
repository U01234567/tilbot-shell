"""The bridge: everything between the shell and Tilbot.

- /chat shows Tilbot in an iframe, with a signed participant token in its URL.
- /bridge/save and /bridge/log are called by Tilbot from inside the Docker network.
  Caddy keeps /bridge/ off the internet; BRIDGE_SECRET and the token protect it as well.

docs/architecture.md describes the contract field by field.
"""
