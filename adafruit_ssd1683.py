# SPDX-FileCopyrightText: 2017 Scott Shawcroft, written for Adafruit Industries
# SPDX-FileCopyrightText: Copyright (c) 2025 Scott Shawcroft for Adafruit Industries
#
# SPDX-License-Identifier: MIT
"""
`adafruit_ssd1683`
================================================================================

CircuitPython `displayio` driver for SSD1683-based ePaper displays


* Author(s): Scott Shawcroft

Implementation Notes
--------------------

**Software and Dependencies:**

* Adafruit CircuitPython firmware for the supported boards:
  https://github.com/adafruit/circuitpython/releases

"""

from epaperdisplay import EPaperDisplay

try:
    import typing

    from fourwire import FourWire
except ImportError:
    pass


__version__ = "0.0.0+auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_CircuitPython_SSD1683.git"

_START_SEQUENCE = (
    b"\x12\x80\x00\x32"  # soft reset and wait 50ms
    b"\x21\x00\x02\x40\x00"  # Display update control 1 & 2
    b"\x3c\x00\x01\x05"  # border waveform control
    b"\x11\x00\x01\x03"  # Ram data entry mode
    b"\x18\x00\x01\x80"  # temp control
    b"\x01\x00\x03\x00\x00\x00"  # driver output control
)

_DISPLAY_UPDATE_MODE = b"\x22\x00\x01\xf7"  # display update mode

_STOP_SEQUENCE = b"\x10\x80\x01\x01\x64"  # Deep Sleep


# Panel-specific extra init bytes and waveform LUTs, ported from
# Adafruit_EPD's Arduino panel headers. These let SSD1683 drive 4-level
# greyscale (``grayscale=True``) on panels whose factory LUT is a mono
# waveform — without the panel-specific waveform LUT loaded via 0x32 plus
# the extra ``Display Mode 2`` bit (0xCF) in command 0x22 the chip just
# runs the mono waveform with both RAMs active and collapses the four
# luma levels to two.
#
# Use as::
#
#     SSD1683(
#         bus, width=400, height=300, busy_pin=epd_busy,
#         grayscale=True,
#         extra_init=THINKINK_420_GRAYSCALE4_MFGN_INIT,
#         custom_lut=THINKINK_420_GRAYSCALE4_MFGN_LUT,
#     )

# Extra start-sequence commands beyond the chip default. Each entry is
# ``cmd, count_hi, count_lo, *data`` (the same byte-packed form as
# ``_START_SEQUENCE``). Three of these (border 0x3C, end-option 0x18) also
# appear in the default ``_START_SEQUENCE`` with mono-waveform values; the
# panel honours the last write so re-issuing them here is intentional.
THINKINK_420_GRAYSCALE4_MFGN_INIT = (
    b"\x3c\x00\x01\x03"  # Border waveform control (greyscale value)
    b"\x0c\x00\x04\x8b\x9c\xa4\x0f"  # Booster soft-start
    b"\x18\x00\x01\x07"  # End option (override mono 0x80)
    b"\x03\x00\x01\x17"  # Gate driving voltage
    b"\x04\x00\x03\x41\xa8\x32"  # Source driving voltage
    b"\x2c\x00\x01\x30"  # Write VCOM register
)

# 227-byte greyscale waveform LUT verbatim from
# ``Adafruit_EPD/src/panels/ThinkInk_420_Grayscale4_MFGN.h``
# (``ti_420mfgn_gray4_lut_code``). Pass to ``SSD1683(custom_lut=...)``.
# fmt: off
THINKINK_420_GRAYSCALE4_MFGN_LUT = bytes((
    0x01, 0x0A, 0x1B, 0x0F, 0x03, 0x01, 0x01, 0x05, 0x0A, 0x01,
    0x0A, 0x01, 0x01, 0x01, 0x05, 0x08, 0x03, 0x02, 0x04, 0x01, 0x01, 0x01,
    0x04, 0x04, 0x02, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x0A, 0x1B, 0x0F,
    0x03, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01, 0x05, 0x48,
    0x03, 0x82, 0x84, 0x01, 0x01, 0x01, 0x84, 0x84, 0x82, 0x00, 0x01, 0x01,
    0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x01, 0x0A, 0x1B, 0x8F, 0x03, 0x01, 0x01, 0x05, 0x4A, 0x01,
    0x8A, 0x01, 0x01, 0x01, 0x05, 0x48, 0x83, 0x82, 0x04, 0x01, 0x01, 0x01,
    0x04, 0x04, 0x02, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x8A, 0x1B, 0x8F,
    0x03, 0x01, 0x01, 0x05, 0x4A, 0x01, 0x8A, 0x01, 0x01, 0x01, 0x05, 0x48,
    0x83, 0x02, 0x04, 0x01, 0x01, 0x01, 0x04, 0x04, 0x02, 0x00, 0x01, 0x01,
    0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x01, 0x01, 0x01, 0x8A, 0x9B, 0x8F, 0x03, 0x01, 0x01, 0x05, 0x4A, 0x01,
    0x8A, 0x01, 0x01, 0x01, 0x05, 0x48, 0x03, 0x42, 0x04, 0x01, 0x01, 0x01,
    0x04, 0x04, 0x42, 0x00, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01,
    0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00,
    0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00,
    0x00,
))
# fmt: on
assert len(THINKINK_420_GRAYSCALE4_MFGN_LUT) == 227


# pylint: disable=too-few-public-methods
class SSD1683(EPaperDisplay):
    r"""SSD1683 driver

    :param bus: The data bus the display is on
    :param \**kwargs:
        See below

    :Keyword Arguments:
        * *width* (``int``) --
          Display width
        * *height* (``int``) --
          Display height
        * *rotation* (``int``) --
          Display rotation
    """

    def __init__(
        self,
        bus: FourWire,
        custom_lut: bytes = b"",
        extra_init: bytes = b"",
        **kwargs,
    ) -> None:
        stop_sequence = bytearray(_STOP_SEQUENCE)
        try:
            bus.reset()
        except RuntimeError:
            # No reset pin defined, so no deep sleeping
            stop_sequence = b""

        load_lut = b""
        display_update_mode = bytearray(_DISPLAY_UPDATE_MODE)
        if custom_lut:
            load_lut = b"\x32" + len(custom_lut).to_bytes(2) + custom_lut
            # Display Update Control 2 = 0xCF: enable clock + analog, run
            # the *Display Mode 2* refresh path (bit 3) so the LUT we just
            # pushed via 0x32 is the one driving the panel. Previously this
            # set 0xC7 which is Display Mode 1 — i.e. the chip's mono
            # waveform, which silently ignores the custom LUT and prevents
            # any 4-level greyscale rendering.
            display_update_mode[-1] = 0xCF

        start_sequence = bytearray(_START_SEQUENCE + extra_init + load_lut + display_update_mode)

        width = kwargs["width"]
        height = kwargs["height"]
        if "rotation" in kwargs and kwargs["rotation"] % 180 != 90:
            width, height = height, width

        if "highlight_color" in kwargs or "grayscale" in kwargs:
            # Enable color RAM
            start_sequence[7] = 0
        if "highlight_color" in kwargs:
            # Switch refresh mode
            display_update_mode[-1] = 0xF7
        start_sequence[len(_START_SEQUENCE) - 3] = (width - 1) & 0xFF
        start_sequence[len(_START_SEQUENCE) - 2] = ((width - 1) >> 8) & 0xFF

        # Greyscale4 LUT convention (matches Adafruit_EPD's
        # ``ThinkInk_420_Grayscale4_MFGN`` panel header): the lighter
        # mid-tone is encoded as ``(black_RAM=0, color_RAM=1)`` and the
        # darker mid-tone as ``(1, 0)``. displayio's grayscale palette
        # quantiser sends *luma bit 7* on pass 0 (the black-RAM command)
        # and *luma bit 6* on pass 1 (the color-RAM command), which gives
        # the opposite mid-tone bits. Swap the two commands when
        # ``grayscale=True`` so the LUT sees the bit pair it expects;
        # white (1,1) and black (0,0) are unaffected. See
        # ``docs/grayscale4-lut-followup.md`` for an alternative fix
        # path (modifying the LUT data) that needs further work.
        write_black = 0x24
        write_color = 0x26
        if kwargs.get("grayscale"):
            write_black, write_color = write_color, write_black

        super().__init__(
            bus,
            start_sequence,
            stop_sequence,
            **kwargs,
            colstart=0,
            # Although the docs say ram_width is in pixels, it determines the wrong
            # number of bytes in the address. So, provide number of bytes.
            ram_width=400 // 8,
            ram_height=300,
            busy_state=True,
            write_black_ram_command=write_black,
            write_color_ram_command=write_color,
            set_column_window_command=0x44,
            set_row_window_command=0x45,
            set_current_column_command=0x4E,
            set_current_row_command=0x4F,
            refresh_display_command=0x20,
            always_toggle_chip_select=False,
            address_little_endian=True,
            two_byte_sequence_length=True,
        )
