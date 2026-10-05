"""Articulated bodies: joints, bones, poses and the physics for when a body goes limp.

Pure Python. Nothing here imports pygame or the simulation.
"""

from skeleton.character import BodyPart, Character, Mode
from skeleton.plan import SkeletonPlan, builtin_plan, load_plan
from skeleton.rig import Bone, Joint, Skeleton

__all__ = ["BodyPart", "Bone", "Character", "Joint", "Mode", "Skeleton", "SkeletonPlan", "builtin_plan", "load_plan"]
