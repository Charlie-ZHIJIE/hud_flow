import asyncio
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEST_MODE = os.environ.get("MCP_TESTING_MODE", "1") in ["1", "true"]

if TEST_MODE:
    XFCE_STARTUP_DELAY = 5
    CHROMIUM_STARTUP_DELAY = 3
else:
    XFCE_STARTUP_DELAY = 30
    CHROMIUM_STARTUP_DELAY = 5


async def start_dinit():
    """Start dinit services if available, otherwise skip."""
    dinit_path = Path("/etc/dinit.d")
    
    if not dinit_path.exists():
        logger.info("No dinit.d directory found, skipping dinit startup")
        return
    
    try:
        from .manual_dinit import ServiceLoader, SimpleDinit
        
        logger.info("Starting dinit")
        loader = ServiceLoader(dinit_path)
        services = loader.load_all()
        engine = SimpleDinit(services)
        engine.start("boot")
    except Exception as e:
        logger.warning(f"Failed to start dinit: {e}, continuing without it")