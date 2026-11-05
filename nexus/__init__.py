"""NEXUS AIS v2.0 - research, paper-trading and shadow-portfolio system.

Stage 0 (build and verify): this package has NO broker write access, NO money
movement and NO live-trading capability. It is intentionally isolated from the
legacy ``core`` / ``strategies`` packages: nothing under ``nexus`` may import
them (enforced by tests/nexus/test_launch_boundary.py).
"""

__version__ = "2.0.0-m1"
SPEC_VERSION = "2.0.0"
