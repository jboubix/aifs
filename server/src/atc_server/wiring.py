"""Connect the decision modules to the bus. Called once per process, before sessions start."""

from .context import AppContext
from .controller import Controller
from .gateway.hub import Hub
from .intent import IntentService
from .monitor import ConformanceMonitor
from .phraseology import Phraseology


def wire(ctx: AppContext) -> None:
    if ctx.wired:
        return
    ctx.wired = True
    IntentService(ctx.bus)
    Controller(ctx.bus, ctx.world, ctx.clearances, ctx.settings)
    Phraseology(ctx.bus)
    ConformanceMonitor(ctx.bus, ctx.clearances, ctx.settings)
    Hub(ctx)
