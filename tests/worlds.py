"""Worlds that more than one module of tests wants made the same way."""

from simulation.world import SimulationWorld


def no_store(world: SimulationWorld) -> SimulationWorld:
    """The same settlement with no store in it (S53): everything is kept where it was before
    there was one, in the pantries, the tank, the cabinet and the heaps. For what is tested of
    those places as they are by themselves, which is how a settlement that has built no store
    still goes."""
    for object_id in [each for each, placed in world.interactables.items() if world.definition_of(placed).store]:
        del world.interactables[object_id]
        world.containers.pop(object_id, None)
    return world
