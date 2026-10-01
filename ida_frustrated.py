# Copyright (c) 2026 Elias Bachaalany
# SPDX-License-Identifier: LicenseRef-Human-Origin-Source-1.0
#
# This file is licensed under the Human-Origin Source License v1.0.
# See LICENSE.

"""IDA Frustrated plugin entry point. Ctrl+Alt+T cycles effects on the active widget.
by Elias Bachaalany
"""

from __future__ import annotations

import ida_idaapi

import core


class IdaFrustratedPlugin(ida_idaapi.plugin_t):
    flags = ida_idaapi.PLUGIN_KEEP
    comment = "Animate the active widget when you're frustrated."
    help = "Press Ctrl+Alt+T. Drop .py files into effects/ or scenes/ to add animations."
    wanted_name = "IDA Frustrated"
    wanted_hotkey = "Ctrl-Alt-T"

    def init(self):
        core.load_animations()
        return ida_idaapi.PLUGIN_KEEP

    def run(self, arg):
        core.frustrate()

    def term(self):
        pass


def PLUGIN_ENTRY():
    return IdaFrustratedPlugin()
