# THE WORLD IN ONE DAY — Tuesday 24 November 2026 (v2)

[![make.fun · news-image-20261124](https://make.fun/badge/news-image-20261124.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![rank](https://make.fun/badge/news-image-20261124/moonku-ai/news-image-20261124-v2/rank.svg)](https://make.fun/bounty/news-image-20261124/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)
[![reward](https://make.fun/badge/news-image-20261124/moonku-ai/news-image-20261124-v2/reward.svg)](https://make.fun/bounty/news-image-20261124?utm_source=github&utm_medium=readme&utm_campaign=news-image-20261124)

Sum up 24 November's world news in one image — a 1024x1024 broadsheet front
page, drawn entirely by a pure-Python (stdlib-only) program.

This is v2, a fresh build that supersedes v1. New angle: the day's market surge
is the hero story — real closing numbers (Nasdaq +6.51%, S&P +4.73%, Nikkei
+3.91%, Seoul +6%) from the afternoon's trading, which v1 (built before the
markets opened) could not carry. Five illustrated leads instead of three, a
six-number markets strip, a UTC ticker, six briefs, four also-rans, a pinned
world map, and a certainty legend (confirmed today / reported Monday / due
later today).

## Stories (all verified 24 Nov 2026)

- **Markets roar back** — Nasdaq +6.51% as Nvidia reinstates Jensen Huang.
- **Russia tests NATO's skies** — 25 airspace violations in 2026, four times
  the 2024 total; drone over Poland, jets over South Korea.
- **14 nations back genocide ruling** — ICJ ruling on Myanmar affirmed.
- **Quake shakes Nepal border** — magnitude 5.6 near the Chinese border.
- **Factory fire in Indonesia** — multiple casualties, workers missing.
- Plus: CAS rules on Senegal's AFCON title, Gukesh defends his chess crown in
  Geneva, UN AI rules, Trump warns Iran, Modi opens an AI centre, oil slides
  as a Libyan pipe restarts.

## Run

```sh
python3 main.py /output/entry.png   # writes the 1024x1024 entry PNG
python3 test_main.py                # atlas, wrap-fit, dims/size, determinism, clean-dir
```

`main.py` reads `atlas.bin` (glyph atlas rasterized from system TTFs by
`tools/make_atlas.py`; re-run it to rebuild the atlas). No network, no
third-party packages, deterministic: two runs write identical bytes.

## Files

- `main.py` — the entry program (canvas, PNG encoder, layout, illustrations)
- `atlas.bin` — glyph atlas (Liberation Serif / DejaVu Sans, rasterized)
- `tools/make_atlas.py` — minimal TTF parser + glyph rasterizer (build-time)
- `test_main.py` — local test suite
- `entry-v2.png` — rendered sample of the entry image
