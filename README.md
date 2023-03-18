# tuneconvert
Convert your favorite tunes from one platform to another with ease. Say goodbye to the hassle of manually transferring your playlists.

If an international identifier (e.g. ISRC) is not available as metadata, several advanced algorithms will try to find the song in international databases. These algorithms include Title string filtering, Shazam and other. The results of these will be scored and ranked to make sure the right song was found.

## Dependencies ([help](https://github.com/szalovszky/tuneconvert/wiki/Installing-dependencies))
- Python (>3.8)
- yt-dlp
- ffmpeg
- pip packages in `requirements.txt`

## Install
Firstly, clone & enter the repository
```bash
git clone https://github.com/szalovszky/tuneconvert && cd tuneconvert
```
Install the required pip packages using
```bash
pip install -r requirements.txt
```
Lastly, launch it
```bash
python main.py <SourceURL> <DestinationPlatform>
```

## Usage
Read more [on the wiki](https://github.com/szalovszky/tuneconvert/wiki)
