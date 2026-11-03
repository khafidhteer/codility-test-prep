# -*- coding: utf-8 -*-
"""Deterministic option ordering for multiple-choice items.

Authored content tends to put the correct answer second, and a bank where 70% of
answers are option B is a guessing strategy rather than a test. Shuffling at build
time, seeded by item id, fixes the position bias while keeping builds reproducible.
"""
import random


def balanced_options(item):
    """Return (options, answer_index) with the options in a stable shuffled order."""
    rnd = random.Random(7000 + int(item["id"].split("-")[1]))
    order = [0, 1, 2, 3]
    rnd.shuffle(order)
    return [item["options"][i] for i in order], order.index(item["answer"])
