# Simulation Rules

This directory contains pure gameplay simulation.

## Forbidden dependencies
Do not import pygame, scenes, UI, renderers or audio playback modules.

## Time and randomness
- Use game time, not wall-clock time.
- Use `SimulationRNG`; never call Python's global random functions from simulation code.

## Side effects
Simulation objects must not render, play sounds, open UI, or access the database/filesystem directly.
They may emit plain domain events.

## Tests
Every new behavioural system needs deterministic tests for its important rules.
