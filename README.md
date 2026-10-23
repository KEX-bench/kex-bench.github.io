# KEX-bench Leaderboard

Static GitHub Pages website for KEX-bench, accepted to EMNLP 2026 Main.

The website uses the [SEC-bench website template](https://github.com/SEC-bench/sec-bench.github.io) (revision `dd300c9f7744c5c7b0020cd1faf0461063213f8c`). Shared styles, navigation, leaderboard controls, run-detail layout, and citation components retain the SEC-bench design. The template is distributed under the included Apache-2.0 license.

## Quick Start

```bash
make install
make build
make serve
```

The local server runs at `http://localhost:8888`. Override with `make serve PORT=8000`.
The build requires Jinja2 from `requirements.txt`.
