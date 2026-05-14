# SPDX-FileCopyrightText: Copyright (c) 2025 Tyeth Gundry for Adafruit Industries
#
# SPDX-License-Identifier: Unlicense

"""4-level greyscale demo for the 4.2" 400x300 ThinkInk_420_Grayscale4_MFGN.

Renders four full-width horizontal bands at white / light grey / dark grey /
black so the panel's four-level waveform LUT can be sanity-checked
visually. Greyscale4 needs three pieces working together: ``grayscale=True``
(enables the 2-bit-per-pixel framebuffer encoding), ``extra_init`` (panel-
specific boost / gate / source / VCOM commands the chip default omits), and
``custom_lut`` (the 227-byte waveform LUT for this particular panel — without
it the chip runs the mono waveform and the four levels collapse to two).
"""

import time

import board
import busio
import displayio
from fourwire import FourWire

import adafruit_ssd1683

displayio.release_displays()

if "EPD_MOSI" in dir(board):  # Feather RP2040 ThinkInk
    spi = busio.SPI(board.EPD_SCK, MOSI=board.EPD_MOSI, MISO=None)
    epd_cs = board.EPD_CS
    epd_dc = board.EPD_DC
    epd_reset = board.EPD_RESET
    epd_busy = board.EPD_BUSY
else:
    spi = board.SPI()  # Uses SCK and MOSI
    epd_cs = board.D9
    epd_dc = board.D10
    epd_reset = board.D8  # Set to None for FeatherWing
    epd_busy = board.D7  # Set to None for FeatherWing

display_bus = FourWire(spi, command=epd_dc, chip_select=epd_cs, reset=epd_reset, baudrate=1000000)
time.sleep(1)

display = adafruit_ssd1683.SSD1683(
    display_bus,
    width=400,
    height=300,
    busy_pin=epd_busy,
    grayscale=True,
    extra_init=adafruit_ssd1683.THINKINK_420_GRAYSCALE4_MFGN_INIT,
    custom_lut=adafruit_ssd1683.THINKINK_420_GRAYSCALE4_MFGN_LUT,
)

# 4-entry palette spanning the panel's four levels. Indices map
# monotonically luma -> grey level: 0 = white, 3 = black.
bitmap = displayio.Bitmap(display.width, display.height, 4)
palette = displayio.Palette(4)
palette[0] = 0xFFFFFF
palette[1] = 0xAAAAAA
palette[2] = 0x555555
palette[3] = 0x000000

band_height = display.height // 4
for band in range(4):
    for y in range(band * band_height, (band + 1) * band_height):
        for x in range(display.width):
            bitmap[x, y] = band

group = displayio.Group()
group.append(displayio.TileGrid(bitmap, pixel_shader=palette))
display.root_group = group

display.refresh()
print("refreshed")

time.sleep(display.time_to_refresh + 5)
print("waited correct time")

# Keep the display the same
while True:
    time.sleep(10)
