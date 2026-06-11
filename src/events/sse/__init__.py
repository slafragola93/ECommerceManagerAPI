"""Server-Sent Events bridge for client-facing real-time updates."""

from .sse_fanout_service import SseFanoutService, attach_sse_fanout

__all__ = ["SseFanoutService", "attach_sse_fanout"]
