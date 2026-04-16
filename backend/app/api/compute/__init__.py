from .flavors import router as flavors_router
from .images import router as images_router
from .instances import router as instances_router
from .keypairs import router as keypairs_router

__all__ = ["instances_router", "keypairs_router", "images_router", "flavors_router"]
