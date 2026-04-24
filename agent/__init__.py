"""Conversion Engine — the agent and all integrations.

Every outbound message passes through agent.kill_switch.deliver(). No code
path outside that function (and its thin channel adapters) may call a
provider SDK's send method directly. See agent/kill_switch.py.
"""

__version__ = "0.1.0"
