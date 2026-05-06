# Greyscale4 LUT vs RAM-command swap — follow-up notes

Background for the conditional `write_black_ram_command` ↔ `write_color_ram_command` swap that fires when `grayscale=True` is passed to `SSD1683`. The swap is the minimal fix that gets four monotonic grey levels rendering on the ThinkInk_420_Grayscale4_MFGN panel; an alternative fix — modifying the panel-specific LUT data so no command swap is needed — was considered and is **not** implemented because the LUT-side experiment we ran was inconclusive. This doc records what we tried so the next person doesn't have to start from scratch.

## What displayio sends

Blinka `displayio` (and the firmware C version) implements `grayscale=True` in `EPaperDisplay._refresh_area` as a two-pass write of bit 7 then bit 6 of the source-pixel luma:

- pass 0 → `write_black_ram_command` (default `0x24`), bit 7 of luma
- pass 1 → `write_color_ram_command` (default `0x26`), bit 6 of luma

So for each pixel the chip sees a `(B=luma>>7&1, R=luma>>6&1)` bit pair:

| RGB888 | luma | (B, R) sent |
| --- | --- | --- |
| `0xFFFFFF` | 255 | (1, 1) |
| `0xAAAAAA` | 170 | (1, 0) |
| `0x555555` | 85  | (0, 1) |
| `0x000000` | 0   | (0, 0) |

## What the panel's LUT expects

`Adafruit_EPD/src/panels/ThinkInk_420_Grayscale4_MFGN.h` declares `setBlackBuffer(0, true) + setColorBuffer(1, true)` and `layer_colors[]` as `WHITE=0b00, BLACK=0b11, LIGHT=0b01, DARK=0b10`. After the inverts that resolves to RAM bit pairs:

| Logical level | (B_RAM, R_RAM) |
| --- | --- |
| WHITE | (1, 1) |
| LIGHT | (0, 1) |
| DARK  | (1, 0) |
| BLACK | (0, 0) |

i.e. the lighter mid-tone is `(0, 1)` and the darker mid-tone is `(1, 0)`, the **opposite** of what `displayio` produces from a monotonic luma palette.

White and black are at the diagonal so they line up. Mid-tones are mismatched.

## Two ways to bridge the gap

1. **RAM-command swap (current)** — when `grayscale=True`, pass `write_black_ram_command=0x26, write_color_ram_command=0x24` to `EPaperDisplay`. This routes displayio's pass-0 bits (luma bit 7) into the panel's "color" RAM and its pass-1 bits (luma bit 6) into the panel's "black" RAM, i.e. it inverts the bit-pair ordering for the LUT. Verified end-to-end on hardware; produces monotonic four levels.

2. **LUT data swap (future)** — modify `THINKINK_420_GRAYSCALE4_MFGN_LUT` so that `(B=1, R=0)` lights the lighter mid-tone and `(B=0, R=1)` lights the darker one. Then the LUT matches displayio's natural bit ordering and option 1's swap goes away.

The second option is structurally cleaner — it keeps the SSD1683 driver's command kwargs at their canonical values and pushes the panel-specific quirk into the panel-specific data — so it would be the preferred fix if the LUT can be re-derived correctly.

## What we tried for option 2

Visually inspecting the 227-byte LUT, it looks like five repeating sub-blocks. Header markers (`0x?A, 0x1B/0x9B, 0x?F`) appear at byte offsets 0, 42, 84, 126 and 168, suggesting four 42-byte blocks plus a 59-byte trailing block. We hypothesised those blocks were the per-level voltage waveforms for `(B,R)=(0,0)/(0,1)/(1,0)/(1,1)`, addressed by `(B<<1)|R`.

Under that hypothesis, swapping bytes `42..83` ↔ `84..125` should swap LIGHT and DARK rendering. We tested it on a Pi e-Ink Bonnet driving the MFGN panel:

- Original LUT, no command swap: `WHITE → DARK → LIGHT → BLACK` (the bug we're trying to fix).
- LUT bytes 42..83 ↔ 84..125 swapped, no command swap: `LIGHT → DARK → WHITE → BLACK` — *worse*. WHITE moved from band 0 to band 2.
- Original LUT, command swap on: `WHITE → LIGHT → DARK → BLACK` (correct).

So the simple "5 contiguous sections, addressed by bit pair" model is wrong. The SSD168x greyscale4 LUT slots actually hold source-driver waveforms for the BB/BW/WB/WW *transitions* (plus a VCOM slot); the 4-level mapping emerges from the interaction of voltage-selection bits, per-phase frame counts, and per-phase repeat counts spread across the whole 227 bytes. Rearranging just two voltage blocks is not equivalent to renaming two levels.

The single-pass test wasn't exhaustive — we didn't try swapping different ranges, didn't swap the trailing phase/repeat bytes alongside the voltage blocks, and didn't sweep block boundaries. So treat the result as "the obvious two-section swap doesn't work" rather than "no LUT-side fix is possible".

## What would actually be needed

To do option 2 properly someone needs to:

1. Get the SSD1683 / SSD1681 datasheet section on the LUT byte layout for greyscale4 — specifically which bytes carry the source voltage selections, which carry frame counts (`TPxA`/`TPxB`), which carry phase repeats (`RPx`), and which carry the VCOM waveform.
2. Identify all the bytes that participate in the rendering of `(B=1,R=0)` vs `(B=0,R=1)`, including any frame-count or repeat data, and produce a new `THINKINK_420_GRAYSCALE4_MFGN_LUT` constant where those positions are swapped.
3. Verify on real hardware (the MFGN panel on a Pi e-Ink Bonnet works; refresh + visual swatch test is the standard check) that the four levels render monotonically without the command swap.
4. If it works: drop the conditional `write_black_ram_command` / `write_color_ram_command` swap from `SSD1683.__init__` so the kwargs go back to `0x24` / `0x26` unconditionally.

Cross-check the result against the other ThinkInk panels in `Adafruit_EPD/src/panels/`:

- `ThinkInk_154_Grayscale4_M05.h`
- `ThinkInk_154_Grayscale4_T8.h`
- `ThinkInk_213_Grayscale4_MFGN.h`
- `ThinkInk_213_Grayscale4_T5.h`
- `ThinkInk_266_Grayscale4_MFGN.h`
- `ThinkInk_270_Grayscale4_W3.h`
- `ThinkInk_290_Grayscale4_EAAMFGN.h`
- `ThinkInk_290_Grayscale4_T5.h`
- `ThinkInk_420_Grayscale4_MFGN.h` (the one this PR adds)
- `ThinkInk_420_Grayscale4_T2.h`
- `ThinkInk_426_Grayscale4_GDEQ.h`

If any of those use a different `setBlackBuffer`/`setColorBuffer` invert combination or a different `layer_colors` mapping, the bit-pair-to-level relationship is panel-specific and the LUT-side fix would need to be panel-by-panel.
