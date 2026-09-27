<div align="center">
  <img src="gitwatch/static/favicon.svg" width="72" height="72" alt="Git Watch">
  <h1>Git Watch</h1>
  <p>GitHub updates. Delivered to Telegram.</p>
  <p><strong>Python 3.11+ · local web dashboard · Raspberry Pi, Linux and Windows</strong></p>
  <p><a href="#quick-start">Quick start</a> · <a href="#screenshots">Screenshots</a> · <a href="README.ru.md">Русский</a></p>
</div>

---

Watch GitHub repositories and get Telegram notifications when branches change. Choose the branches and polling interval for each repository; Git Watch keeps checking while your browser is closed.

![Git Watch dashboard with monitored repositories, Telegram status and recent changes](assets/screenshots/dashboard.png)

<p align="center"><sub>Actual interface with demonstration data. The application UI is currently in Russian.</sub></p>

## Features

| Feature | What it does |
| --- | --- |
| Flexible monitoring | Public or private repositories; all branches, the default branch or one selected branch |
| Telegram notifications | Commit summaries and links, delivery retries, and repository setup with `/add` |
| Persistent history | SQLite storage, a 90-day event history and a queue that survives restarts |
| Desktop and phone | Responsive dashboard, manual checks, pause controls and optional Telegram proxy |

## Quick start

Install **Python 3.11+**, clone this repository or download **Code → Download ZIP**, and open a terminal in the project folder.

**Linux / macOS**

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python run.py
```

<details>
<summary>Windows (PowerShell)</summary>

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

</details>

Open **http://127.0.0.1:8788**. Keep the process running; press `Ctrl+C` to stop it.

1. In **Settings / Настройки**, enter a dedicated [BotFather](https://t.me/BotFather) bot token and your Telegram username. Save, then send `/start` to your bot.
2. Add a GitHub token if you need private repositories or a higher request limit. A fine-grained token needs **Contents: Read-only** for the selected repositories.
3. Click **Add / Добавить**, paste a repository URL, and choose branches and an interval. The first check establishes a baseline; notifications start with subsequent changes.

## Screenshots

| Choose a branch and interval | Connect Telegram and GitHub |
| --- | --- |
| [![Repository setup with a branch selected](assets/screenshots/repository-setup.png)](assets/screenshots/repository-setup.png) | [![Connection settings with empty token fields and demo account details](assets/screenshots/settings.png)](assets/screenshots/settings.png) |

<details>
<summary>On your phone</summary>
<p align="center"><a href="assets/screenshots/mobile.png"><img src="assets/screenshots/mobile.png" width="360" alt="Git Watch dashboard on a phone"></a></p>
</details>

## Run automatically on Raspberry Pi / Linux

On Debian / Ubuntu, run these commands from the project folder:

```bash
sudo apt install -y python3 python3-venv git
sudo bash scripts/install.sh
```

This creates a systemd service bound to localhost. To use a trusted LAN, pass your device's private IP as the first argument to `install.sh`. For an installed Git checkout, update with `bash scripts/update.sh`.

**The dashboard has no login. Keep it on localhost or a trusted LAN; do not expose it directly to the internet.** Tokens and settings are stored in `data/`, which is excluded from Git. Optional Telegram proxy URLs go in `data/telegram-proxy.json` under the `http` and `https` keys. Back up private data with `.venv/bin/python scripts/backup.py`; keep the resulting `backups/` archives private.
