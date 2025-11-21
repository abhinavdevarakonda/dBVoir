# Windows Setup Instructions

## Prerequisites

1. **Python 3.8+**

2. **FFmpeg** (optional, for replaygain):

## Installation

1. Clone/download the project to your Windows PC

2. Open PowerShell/CMD in project directory

3. Create virtual environment:
   
   python -m venv venv
   venv\Scripts\Activate.ps1  # or venv\Scripts\activate.bat
   4. Install dependencies:
 ll
   pip install -r requirements.txt
   5. For optional features:ershell
   pip install langdetect pylast
   6. Create `.env` file:
   
   JELLYFIN_URL=http://10.0.0.8:8096
   JELLYFIN_API_KEY=your_api_key_here
   7. Test Beets:l
   beet -c beets-config/config.yaml config
   8. Run the automation:hell
   python automation/dbvoir.py
   ## Troubleshooting

- If `beet` command not found, use: `python -m beets`
- For replaygain with ffmpeg, ensure FFmpeg is in PATH
- Make sure directories exist: `C:\media\music\incoming\soulseek` and `C:\media\music\library`