# Greyscale4 LUT follow-up notes

Background for the 4-level greyscale support on the
ThinkInk_420_Grayscale4_MFGN panel.

The first draft of this PR used a conditional RAM-command swap when
`grayscale=True` was passed to `SSD1683`: displayio pass 0 was written with
command `0x26` and pass 1 with command `0x24`. That worked on hardware, but it
put a panel-specific LUT quirk into the generic SSD1683 command setup.

The current approach keeps the SSD1683 RAM commands canonical:

- `write_black_ram_command = 0x24`
- `write_color_ram_command = 0x26`

and instead fixes the panel-specific waveform data in
`THINKINK_420_GRAYSCALE4_MFGN_LUT`.

## What displayio sends

Blinka `displayio` and CircuitPython firmware implement `grayscale=True` in
`EPaperDisplay._refresh_area` as a two-pass write of bit 7 then bit 6 of the
source-pixel luma:

- pass 0: `write_black_ram_command` (`0x24`), bit 7 of luma
- pass 1: `write_color_ram_command` (`0x26`), bit 6 of luma

For a monotonic four-entry greyscale palette, the SSD1683 receives:

| RGB888 | luma | (B/W RAM, R RAM) |
| --- | --- | --- |
| `0xFFFFFF` | 255 | (1, 1) |
| `0xAAAAAA` | 170 | (1, 0) |
| `0x555555` | 85 | (0, 1) |
| `0x000000` | 0 | (0, 0) |

## What the SSD1683 datasheet says

SSD1683 Table 6-5, "RAM bit and LUT mapping for black/white display", maps the
two RAM bits to black/white waveform slots:

| R RAM | B/W RAM | Image color | LUT |
| --- | --- | --- | --- |
| 0 | 0 | Black | `LUTBB` |
| 0 | 1 | White | `LUTWB` |
| 1 | 0 | Black | `LUTBW = LUTBB` |
| 1 | 1 | White | `LUTWW = LUTWB` |

SSD1683 command `0x32` writes the 227-byte LUT register. Figure 6-7,
"Waveform Setting format for black/white mode", lays out those bytes as five
42-byte LUT blocks followed by shared frame-rate / XON data:

| Byte range | Slot |
| --- | --- |
| `0..41` | `LUTC` |
| `42..83` | `LUTWW` |
| `84..125` | `LUTBW` |
| `126..167` | `LUTWB` |
| `168..209` | `LUTBB` |
| `210..226` | shared `FR` / `XON` bytes |

That block order is the important correction. The failed draft experiment
swapped bytes `42..83` with `84..125`, which is `LUTWW` <-> `LUTBW`. That
renamed a white transition as one of the mid-tone transitions, so the visual
result moved white into the wrong band.

## Current LUT edit

The current `THINKINK_420_GRAYSCALE4_MFGN_LUT` starts from the Arduino
`Adafruit_EPD/src/panels/ThinkInk_420_Grayscale4_MFGN.h`
`ti_420mfgn_gray4_lut_code` data and swaps only the two black/white mid-tone
transition blocks:

- original bytes `84..125` (`LUTBW`) move to `126..167`
- original bytes `126..167` (`LUTWB`) move to `84..125`

The `LUTC`, `LUTWW`, `LUTBB`, and shared `FR` / `XON` bytes are left unchanged.
The LUT remains 227 bytes.

With that panel-specific LUT correction, displayio can keep its natural pass
ordering and `SSD1683` can keep the standard RAM write commands.

## Hardware check

The required hardware acceptance test is:

1. Run `examples/4_2_inch_400x300_grayscale.py` on the
   ThinkInk_420_Grayscale4_MFGN panel.
2. Confirm the four horizontal bands render as white, light grey, dark grey,
   black, in that order.
3. Confirm the driver is using canonical commands `0x24` for B/W RAM and
   `0x26` for R RAM.

This repository can statically check the LUT length and block movement, but the
actual e-paper greyscale result still needs hardware verification before the PR
is marked ready.
