import argparse
from collections.abc import Sequence

from simulation.world import SimulationWorld

MINUTES_PER_DAY = 24 * 60


def run_headless(days: int, seed: int = 7) -> list[str]:
    world = SimulationWorld.demo_world(seed=seed)
    world.step(days * MINUTES_PER_DAY)
    world.events.drain()
    return world.event_log


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the simulation without pygame.")
    parser.add_argument("--days", type=int, default=1)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args(argv)

    for line in run_headless(days=args.days, seed=args.seed):
        print(line)


if __name__ == "__main__":
    main()
