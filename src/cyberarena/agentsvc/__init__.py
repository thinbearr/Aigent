"""Standalone investigation-agent service.

This is a SEPARATE service from the plant. It never touches the plant's database.
It pulls evidence and change tickets from the plant's read-only HTTP API, then runs
the Orchestrator -> Blue -> Critic -> Forensics engine and returns the verdict with
its full reasoning trace. In Docker it is its own container; it only needs the plant's
URL and the read-only evidence token.
"""
