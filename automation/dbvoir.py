#!/usr/bin/env python3
"""
dBVoir - seamless nicotine+ → beets → jellyfin
monitors nicotine+ downloads, metadata through beets, jellyfin rescan
"""

import os
import sys
import time
import logging
import subprocess
import requests
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from dotenv import load_dotenv

load_dotenv()

jellyfin_api_key = os.getenv('JELLYFIN_API_KEY')
jellyfin_url = os.getenv('JELLYFIN_URL', 'http://10.0.0.8:8096')
nicotine_download_dir = os.getenv('NICOTINE_DOWNLOAD_DIR', r'C:\media\music\incoming\soulseek')
watch_delay = int(os.getenv('WATCH_DELAY', '30'))

# logging
log_dir = Path(r'C:\media\music')
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'dbvoir.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('dBVoir')

CONFIG = {
    'nicotine_download_dir': nicotine_download_dir,
    'beets_binary': 'beet',
    'beets_config': str(Path(__file__).parent.parent / 'beets-config' / 'config.yaml'),
    'jellyfin_url': jellyfin_url,
    'jellyfin_api_key': jellyfin_api_key,
    'jellyfin_library_id': os.getenv('JELLYFIN_LIBRARY_ID', ''),
    'watch_delay': watch_delay,
    'file_extensions': {'.mp3', '.flac', '.m4a', '.ogg', '.opus', '.wav', '.wma'},
}

# track active downloads, avoid processing incomplete files
active_downloads = {}
processed_files = set()


class MusicProcessor(FileSystemEventHandler):
    """Watch for new music files and process them through Beets."""
    
    def __init__(self):
        self.pending_imports = {}
    
    def on_created(self, event):
        if event.is_directory:
            return
        self.handle_file(event.src_path)
    
    def on_modified(self, event):
        if event.is_directory:
            return
        self.handle_file(event.src_path)
    
    def on_closed(self, event):
        if event.is_directory:
            return

        # file write completed
        if event.src_path in self.pending_imports:
            time.sleep(2) # just to make sure it's completed lol
            self.process_file(event.src_path)
    
    def handle_file(self, file_path):
        """Check if file should be processed."""
        path = Path(file_path)
        
        # music only!
        if path.suffix.lower() not in CONFIG['file_extensions']:
            return
        
        # check if file exists
        if not path.exists() or path.stat().st_size == 0:
            return
        
        # skip if already processed
        if str(path) in processed_files:
            return
        
        # check if download is in progress
        try:
            mtime = path.stat().st_mtime
            age = time.time() - mtime
            
            if age < CONFIG['watch_delay']:
                # file too new, might still be downloading
                logger.info(f"File {path.name} is new, waiting before processing...")
                self.pending_imports[str(path)] = time.time()
                return
            
            # file complete
            self.process_file(file_path)
        except (OSError, PermissionError) as e:
            # file might be locked by Nicotine+, skip for now
            logger.debug(f"File {path.name} is locked, will retry later: {e}")
    
    def process_file(self, file_path):
        """Process file through Beets."""
        path = Path(file_path)
        
        if str(path) in processed_files:
            return
        
        logger.info(f"Processing: {path.name}")
        
        try:
            # Import with Beets - import the directory containing the file
            # beets will handle the album organization
            import_path = path.parent if path.is_file() else path
            
            cmd = [
                CONFIG['beets_binary'],
                '-c', CONFIG['beets_config'],
                'import',
                '-q',  # quiet mode
                '--noautotag',  # skip interactive prompts
                '--move',
                str(import_path)
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
                cwd=str(Path(__file__).parent)
            )
            
            if result.returncode == 0 or 'Skipping' in result.stdout or 'not match' in result.stdout:
                logger.info(f"Successfully processed: {path.name}")
                processed_files.add(str(path))
                
                trigger_jellyfin_rescan()
            else:
                logger.warning(f"Beets import returned non-zero exit code for {path.name}")
                logger.debug(f"Beets output: {result.stdout}")
                logger.debug(f"Beets error: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout processing {path.name}")
        except Exception as e:
            logger.error(f"Error processing {path.name}: {e}")
    
    def process_pending(self):
        """Process pending files that might have finished downloading."""
        current_time = time.time()
        to_process = []
        
        for file_path, added_time in list(self.pending_imports.items()):
            if current_time - added_time >= CONFIG['watch_delay']:
                path = Path(file_path)
                try:
                    if path.exists() and path.stat().st_size > 0:
                        # check if file hasn't been modified recently (download complete)
                        mtime = path.stat().st_mtime
                        if current_time - mtime >= 5:
                            to_process.append(file_path)
                except (OSError, PermissionError):
                    continue
        
        for file_path in to_process:
            del self.pending_imports[file_path]
            self.process_file(file_path)


def trigger_jellyfin_rescan():
    # jellyfin refresh with api
    if not CONFIG['jellyfin_api_key']:
        logger.warning("Jellyfin API key not configured, skipping rescan trigger")
        return
    if not CONFIG['jellyfin_url']:
        logger.warning("Jellyfin URL not configured, skipping rescan trigger")
        return
    
    try:
        headers = {
            'X-Emby-Token': CONFIG['jellyfin_api_key'],
            'Content-Type': 'application/json'
        }
        
        # refresh library
        url = f"{CONFIG['jellyfin_url']}/Library/Refresh"
        params = {'Recursive': 'true', 'MetadataRefreshMode': 'Default'}
        
        if CONFIG['jellyfin_library_id']:
            params['ItemIds'] = CONFIG['jellyfin_library_id']
        
        response = requests.post(url, headers=headers, params=params, timeout=10)
        
        if response.status_code in [200, 204]:
            logger.info("Jellyfin library refresh triggered successfully")
        else:
            logger.warning(f"Jellyfin rescan returned status {response.status_code}")
    
    except Exception as e:
        logger.error(f"Failed to trigger Jellyfin rescan: {e}")


def watch_directory():
    # Start watching the Nicotine+ download directory
    watch_path = Path(CONFIG['nicotine_download_dir'])
    
    if not watch_path.exists():
        logger.error(f"Watch directory does not exist: {watch_path}")
        logger.info(f"Please create the directory: {watch_path}")
        return
    
    logger.info(f"Watching directory: {watch_path}")
    logger.info(f"Files will be organized to: C:\\media\\music\\library")
    
    event_handler = MusicProcessor()
    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
            # pending files one by one
            event_handler.process_pending()
    except KeyboardInterrupt:
        logger.info("Stopping watcher...")
        observer.stop()
    
    observer.join()


if __name__ == '__main__':
    logger.info("dBVoir - Starting Nicotine+ → Beets → Jellyfin pipeline")
    logger.info(f"Monitoring: {CONFIG['nicotine_download_dir']}")
    logger.info(f"Target: C:\\media\\music\\library")
    watch_directory()