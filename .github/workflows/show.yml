name: Generate ShowTurk M3U8

on:
  workflow_dispatch:
  schedule:
    - cron: "*/30 * * * *"

permissions:
  contents: write

jobs:
  build:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install streamlink requests

      - name: Run ShowTurk script
        run: python src/showturk.py

      - name: Commit & push if file exists
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

          if [ -f output/showturk.m3u8 ]; then
            git add output/showturk.m3u8
            git diff --cached --quiet || git commit -m "Update ShowTurk stream"
            git push
          else
            echo "No stream file generated → skip commit"
          fi
