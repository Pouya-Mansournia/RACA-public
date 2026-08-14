# RACA: Robotic Adaptive Cognitive Architecture

This is the isolated workspace for the new research program (see
`docs/research_lineage.md` for how it grew out of Paper 1). All new RACA
code lives here, kept separate from the read-only Phase-I evidence and
code elsewhere in this repository.

Nothing in this directory may import `rclpy`, ROS message types, Nav2
actions, or Gazebo APIs at the `raca_core` level. ROS 2 belongs only in
`raca_adapters/`.

Status: the workspace has moved well past its original Phase 0 setup.
`raca_core`, the routing layer, the lightweight simulator, and the
statistics tooling are all in place.
