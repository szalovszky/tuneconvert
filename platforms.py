import traceback
import time
import re
import deezer
import requests
from bs4 import BeautifulSoup
from time import sleep
import random
import os

import yt_dlp
import ffmpeg
from shazamio import Shazam

import constants
from utils import data, music_data
import platforms
import settings
import objects

class deezer_platform:
    deezer_client = deezer.Client()

    def download(url, path, isrc=""):
        path = f"{path}deezer{isrc}.wav"
        if(not os.path.exists(path)):
            ydl_opts = {
                'format': 'bestaudio/best',
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'wav',
                }],
                'outtmpl': path,
                'logger': settings.download_logger,
                "ignoreerrors": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
                try:
                    ytdl.download(url)
                except Exception:
                    return None

    def search_track(query):
        success = False
        while(not success):
            try:
                try:
                    iterator = iter(query)
                except TypeError:
                    pass
                else:
                    query = " ".join(query)
                if(len(query) <= 2):
                    return False
                res = platforms.deezer_platform.deezer_client.search(query)
                if(len(res) <= 0):
                    res = None
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    data.prnt(traceback.format_exc())
                    res = None
                    break
        return res

    def isrc(isrc):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.request("GET", "track/isrc:" + isrc, resource_type=deezer.Track)
                success = True
            except Exception as e:
                e = str(e).lower()
                if("quota" in e):
                    time.sleep(1)
                else:
                    if("no data" not in e):
                        data.prnt(traceback.format_exc())
                    res = None
                    break
        return res

    def trackid(id):
        success = False
        while(not success):
            try:
                res = platforms.deezer_platform.deezer_client.request("GET", "track/" + id, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    if("no data" not in e):
                        data.prnt(traceback.format_exc())
                    res = None
                    break
        return res

    def tracklink(url):
        success = False
        while(not success):
            try:
                # I know this can be done fully by RegEx, but I can't into RegEx
                id = re.sub(r'(?<=https://www.deezer.com/).*(?=/track/)', '', url).replace("https://www.deezer.com//track/", "")
                res = platforms.deezer_platform.deezer_client.request("GET", "track/" + id, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    if("no data" not in e):
                        data.prnt(traceback.format_exc())
                    res = None
                    break
        return res

    def search_album(query):
        success = False
        while(not success):
            try:
                if(len(query) <= 2):
                    return False
                res = platforms.deezer_platform.deezer_client.request("GET", "search/album?q=" + query, resource_type=deezer.Album)
                if(len(res) > 0):
                    res = res[0].as_dict()
                    if(res['record_type'] == "single" and res['tracklist'] != ""):
                        res = platforms.deezer_platform.deezer_client.request("GET", res['tracklist'].replace("https://api.deezer.com/", ""))
                        if(len(res) > 0):
                            res = res[0]
                        else:
                            res = None
                    else:
                        res = None
                else:
                    res = None
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    data.prnt(traceback.format_exc())
                    res = None
                    break
        return res

    def check_result(query, result, featured_artists=False, music_type=objects.music.type.DEFAULT):
        if((result is None) or (result is False)):
            return False
        seperate = isinstance(query, list)

        try:
            if(type(result) is dict):
                raise TypeError
            iterator = iter(result)
        except TypeError:
            result_item = result
            try:
                result_item = result_item.as_dict()
            except Exception:
                pass
            if(seperate):
                if("title" not in result_item): return False
                artist = result_item['artist']['name']
                if(featured_artists):
                    if("contributors" not in result_item):
                        result_item = platforms.deezer_platform.trackid(str(result_item['id']))
                        try:
                            result_item = result_item.as_dict()
                        except Exception:
                            pass
                    artist_sum = ""
                    for m_artist in result_item['contributors']:
                        artist_sum += music_data.filter_data(m_artist['name'], "", music_type=music_type)[0] + " "
                    artist = ' '.join(data.unique_list(artist_sum.split()))
                artist_filtered = music_data.filter_data(artist, "", music_type=music_type)[0]
                title_filtered = music_data.filter_data("", result_item['title'], music_type=music_type)[1]
                if("karaoke" in result_item['title'].lower()):
                    return False
                artist_certainty = data.similar(query[0], artist_filtered)
                title_certainty = data.similar(query[1], title_filtered)
                if(((query[0] != "") and(artist_certainty < constants.similarity_threshold)) or (title_certainty < constants.similarity_threshold)):
                    return False
                else:
                    certainty = ((artist_certainty + title_certainty)/2)
                    if((music_type != objects.music.type.REMIX_OR_COVER_OR_INSTRUMENTAL) and (any(trigger in result_item['title'] for trigger in constants.REMIX_OR_COVER_OR_INSTRUMENTAL_triggers))):
                        certainty -= 0.5
                    return [certainty, result_item]
            else:
                result_filtered = " ".join(music_data.filter_data(result_item['artist']['name'], result_item['title'], music_type=music_type))
                if("karaoke" in result_item['title'].lower()):
                    return False
                certainty = data.similar(query, result_filtered)
                if(certainty < constants.similarity_threshold):
                    return False
                else:
                    if((music_type != objects.music.type.REMIX_OR_COVER_OR_INSTRUMENTAL) and (any(trigger in result_item['title'] for trigger in constants.REMIX_OR_COVER_OR_INSTRUMENTAL_triggers))):
                        certainty -= 0.5
                    return [certainty, result_item]
        else:
            most_certain = ["", 0.0, 0.0]
            iterate_success = False
            while(not iterate_success):
                try:
                    for result_item in result:
                        try:
                            result_item = result_item.as_dict()
                        except Exception:
                            pass
                        if(seperate):
                            artist = result_item['artist']['name']
                            if(featured_artists):
                                if("contributors" not in result_item):
                                    result_item = platforms.deezer_platform.trackid(str(result_item['id']))
                                    try:
                                        result_item = result_item.as_dict()
                                    except Exception:
                                        pass
                                artist_sum = ""
                                for m_artist in result_item['contributors']:
                                    artist_sum += music_data.filter_data(m_artist['name'], "", music_type=music_type)[0] + " "
                                artist = ' '.join(data.unique_list(artist_sum.split()))
                            artist_filtered = music_data.filter_data(artist, "", music_type=music_type)[0]
                            title_filtered = music_data.filter_data("", result_item['title'], music_type=music_type)[1]
                            if("karaoke" in result_item['title'].lower()):
                                pass
                            artist_certainty = data.similar(query[0], artist_filtered)
                            title_certainty = data.similar(query[1], title_filtered)
                            if(((query[0] != "") and(artist_certainty < constants.similarity_threshold)) or (title_certainty < constants.similarity_threshold)):
                                pass
                            else:
                                if(artist_certainty > most_certain[1]):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                                if((artist_certainty > most_certain[1]) and (title_certainty > most_certain[2])):
                                    most_certain = [result_item, artist_certainty, title_certainty]
                        else:
                            result_filtered = " ".join(music_data.filter_data(result_item['artist']['name'], result_item['title'], music_type=music_type))
                            if("karaoke" in result_item['title'].lower()):
                                pass
                            certainty = data.similar(query, result_filtered)
                            if(certainty < constants.similarity_threshold):
                                pass
                            else:
                                if(certainty > most_certain[1]):
                                    most_certain = [result_item, certainty, 0.0]
                        break
                    certainty = most_certain[1] if most_certain[2] == 0.0 else ((most_certain[1] + most_certain[2])/2)
                    return [certainty, result_item]
                    iterate_success = True
                except Exception as e:
                    if("quota" in str(e).lower()):
                        time.sleep(1)
                    else:
                        data.prnt(traceback.format_exc())
                        return None

class ddg_platform:
    class result:
        def __init__(self, title, link):
            self.title = title
            self.link = link
        def as_dict(self):
            return self.__dict__

    def search(query):
        success = False
        delay = 2
        while(not success):
            try:
                headers = {
                    'User-Agent': random.choice(constants.user_agents)
                }

                page = requests.get(f"https://html.duckduckgo.com/html/?q={query}", headers=headers)
                res = []
                if("If this error persists, please let us know" in str(page.content)):
                    delay *= 2
                    data.prnt(f"You are being ratelimited, waiting {delay} seconds before retrying...")
                    if(delay >= 30):
                        success = True
                        res = False
                    sleep(delay)
                    continue
                soup = BeautifulSoup(page.content, "html.parser")
                elems = soup.find_all("div", class_="result__body")

                for elem in elems:
                    title = elem.find("a", class_="result__a")
                    if(title == None):
                        continue
                    else:
                        title = title.text
                    link = "https://" + " ".join(elem.find("a", class_="result__url").text.split())
                    res.append(ddg_platform.result(title, link).as_dict())

                success = True
                return res
            except Exception:
                data.prnt(traceback.format_exc())
                return None

    def search_track(query, use_spotify = False):
        if(len(query) <= 4):
            return None

        try:
            res = None
            srch = ddg_platform.search(f"{query} site:{'deezer.com' if (not use_spotify) else 'open.spotify.com'}")
            for srch_res in srch:
                if((not use_spotify and srch_res['link'].startswith("https://www.deezer.com/") and ("/artist/" not in str(srch_res['link'])) and ("/playlist/" not in str(srch_res['link'])) and ("/album/" not in str(srch_res['link']))) or
                (use_spotify and srch_res['link'].startswith("https://open.spotify.com"))):
                    res = srch_res['link']
                    # Remove non-numeric chars
                    res = re.sub("[^0-9]", "", res)
                    if(res == ""):
                        res = None
                    if(res != None):
                        return res

            return res
        except Exception as e:
            data.prnt(e)
            return None

class startpage_platform:
    class result:
        def __init__(self, title, link):
            self.title = title
            self.link = link
        def as_dict(self):
            return self.__dict__
    
    def search(query):
        success = False
        while(not success):
            # An extra precaution to not get ratelimited
            sleep(1)
            try:
                headers = {
                    'User-Agent': random.choice(constants.user_agents)
                }

                page = requests.get(f"https://www.startpage.com/sp/search?query={query}", headers=headers)
                res = []
                soup = BeautifulSoup(page.content, "html.parser")
                elems = soup.find_all("div", class_="w-gl__result__main")

                for elem in elems:
                    title = elem.find("h3").text
                    link = elem.find("a", class_="result-link")['href']
                    res.append(startpage_platform.result(title, link).as_dict())

                success = True
                return res
            except Exception as e:
                data.prnt(e)
                return None

    def search_track(query, use_spotify = False):
        if(len(query) <= 4):
            return None

        try:
            res = None
            srch = startpage_platform.search(f"{query} site:{'deezer.com' if (not use_spotify) else 'open.spotify.com'}")
            for srch_res in srch:
                if((not use_spotify and srch_res['link'].startswith("https://www.deezer.com/") and ("/artist/" not in str(srch_res['link'])) and ("/playlist/" not in str(srch_res['link'])) and ("/album/" not in str(srch_res['link']))) or
                (use_spotify and srch_res['link'].startswith("https://open.spotify.com"))):
                    res = srch_res['link']
                    # Remove non-numeric chars
                    res = re.sub("[^0-9]", "", res)
                    if(res == ""):
                        res = None
                    if(res != None):
                        return res

            return res
        except Exception as e:
            data.prnt(e)
            return None

class youtube_platform:
    class parse_method:
        DEFAULT = 0
        UPLOADER_TITLE = 1
        TITLE_ONLY = 2
    
    def download(url, path):
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }, {
                'key': 'SponsorBlock',
                'categories': ['music_offtopic']
            }, {
                'key': 'ModifyChapters',
                'remove_sponsor_segments': ['music_offtopic']
            }],
            'outtmpl': path.replace('.wav', ''),
            'logger': settings.download_logger,
            "ignoreerrors": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ytdl:
            try:
                ytdl.download(url)
            except Exception:
                return None

    def parse(video, parse_method=parse_method.DEFAULT, music_type=objects.music.type.DEFAULT):
        if(video is None):
            return None
        if(parse_method is youtube_platform.parse_method.DEFAULT):
            # Get Artist and Title field from YouTube
            if("artist" not in video):
                # No copyright field, try to parse it from video title
                x = video['title'].lower().split(" - ")
                if(len(x) > 1):
                    artist = x[0]
                    title = x[1]
                else:
                    artist = ""
                    title = x[0]
            else:
                # There is a copyright field on the video, use that
                artist = video['artist'].lower()
                title = video['track'].lower()
        elif(parse_method is youtube_platform.parse_method.UPLOADER_TITLE):
            artist = video['uploader']
            title = video['title']
        elif(parse_method is youtube_platform.parse_method.TITLE_ONLY):
            artist = ""
            title = video['title']

        return music_data.filter_data(artist=artist, title=title, music_type=music_type)

class shazam_platform:
    async def recognize(filename):
        shazam = Shazam()
        (ffmpeg
            .input(filename, loglevel='16')
            .output(filename + '%00005d.wav',
                    c='copy', map='0', segment_time='00:00:30',
                    f='segment', reset_timestamps='1')
            .run(overwrite_output=True))

        found_isrc = None
        last_isrc = None

        segment = 0
        search = True
        files = sorted(os.listdir(settings.temp_dir))

        for file in files:
            if (file.startswith("audio") and not filename.endswith(file)):
                file = settings.temp_dir + file
                if (search):
                    if(file.endswith(".temp.concat")):
                        continue
                    if (int(file.replace(filename, "").replace(".wav", "")
                            .replace(settings.temp_dir, "")) % 2 == 0):
                        if(segment >= 12):
                            data.prnt(f"Giving up after {segment} tries")
                            break
                        segment += 1
                        data.prnt(f"Testing segment #{segment}...")
                        try:
                            out = await shazam.recognize_song(file)
                            isrc = out['track']['isrc']
                            if(last_isrc == isrc):
                                found_isrc = isrc
                                search = False
                            else:
                                if(last_isrc != "0" and segment != 1):
                                    data.prnt("Different result, continuing...")
                                last_isrc = isrc
                        except Exception:
                            data.prnt("Segment not found.")
                if os.path.exists(file):
                    os.remove(file)
                else:
                    data.prnt(f"Somehow {file} doesn't exist?")
        
        return found_isrc