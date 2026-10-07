# Skeleton Rules
- Pure Python: no pygame, and nothing from `simulation/`, `world/`, `scenes/` or `graphics/`.
- A skeleton is presentation. Which parts a resident has lost is decided and saved by the simulation; this package only shows it.
- Physics runs on real time and is never saved. It must not touch the simulation's RNG or clock.
- The body plan, its limits and its clips are data in `data/skeleton.json`. Code never names a particular joint or bone.
- A body that is merely posed runs no physics. A limp one that lies still goes to sleep.
- A lively body follows its clips on springs (`skeleton/motion.py`): real time, never saved, moved only when the body is looked at. How loose each bone is (`motion`) and which legs keep their feet on the ground (`footing`) are data.
- Springs work on a body facing the unmirrored way. Mirroring comes last, in `SkeletonPlan.place`.
