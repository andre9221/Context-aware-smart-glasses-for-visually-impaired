#!/usr/bin/env python3
"""Compatibility wrapper pointing to pi_hardware_check.py"""
from scripts.pi_hardware_check import main

if __name__ == "__main__":
    raise SystemExit(main())
