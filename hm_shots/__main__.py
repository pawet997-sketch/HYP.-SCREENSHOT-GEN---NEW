# -*- coding: utf-8 -*-
"""``python -m hm_shots [--demo] [--dark] [--lang=en] [session.hmshots.json]``"""
import sys

from .gui.app import run

if __name__ == "__main__":
    run(sys.argv[1:])
