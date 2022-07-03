import asyncio
import traceback
from timeout import TimeoutException

from utils import data
from platforms import *
import constants

class check_result:
    id = ""
    score = 1.0
    result = None

    def __init__(self, id="", score=1.0, result=None):
        self.id = id
        self.score = score
        self.result = result

    def gen(query, result, music_type=objects.music.type.DEFAULT):
        result_check = deezer_platform.check_result(query=query, result=result, music_type=music_type)
        if(result_check is not None):
            if(not result_check):
                return None
        return result if result is None else check_result(id=data.hash(str(result_check)), score=1, result=result_check).__dict__

class deezer_check:
    def track(query, music_type=objects.music.type.DEFAULT):
        if(not settings.settings.no_deezertrack):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            deezer_result = deezer_platform.search_track(query)
            return check_result.gen(query, deezer_result, music_type=music_type)
    
    def album(query, music_type=objects.music.type.DEFAULT):
        if(not settings.settings.no_deezeralbum):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            try:
                iterator = iter(query)
            except TypeError:
                pass
            else:
                query = " ".join(query)
            deezer_result = deezer_platform.search_album(query)
            return check_result.gen(query, deezer_result, music_type=music_type)

class startpage_check:
    def search(query, music_type=objects.music.type.DEFAULT):
        if(not settings.settings.no_startpage):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            deezer_result = None
            startpage_result = startpage_platform.search_track(query, use_spotify=False)
            if(startpage_result is not None):
                deezer_result = deezer_platform.tracklink(startpage_result)
            return check_result.gen(query, deezer_result, music_type=music_type)

class duckduckgo_check:
    def search(query, music_type=objects.music.type.DEFAULT):
        if(not settings.settings.no_ddg):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            deezer_result = None
            ddg_result = ddg_platform.search_track(query, use_spotify=False)
            if(ddg_result is not None):
                deezer_result = deezer_platform.tracklink(ddg_result)
            return check_result.gen(query, deezer_result, music_type=music_type)

loop = asyncio.get_event_loop()

class shazam_check:
    def search(query, filename, music_type=objects.music.type.DEFAULT):
        global loop
        if(not settings.settings.no_shazam):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            deezer_result = None
            shazam = loop.run_until_complete(shazam_platform.recognize(filename))
            if(shazam is not None):
                deezer_result = deezer_platform.isrc(shazam)
            return check_result.gen(query, deezer_result, music_type=music_type)

class external_check:
    def links(query, description, music_type=objects.music.type.DEFAULT):
        if(not settings.settings.no_links):
            data.hookout(type="status", status="check", check=data.get_caller(__class__))
            deezer_result = None
            try:
                links = music_data.check_links(description.replace("\n", " "))
                if(links is not None):
                    if(links[0] is not None):
                        id = links[0]
                        deezer_result = deezer_platform.trackid(id)
                    elif(links[1] is not None):
                        isrc = links[1]
                        deezer_result = deezer_platform.isrc(isrc)
            except TimeoutException as te:
                data.prnt(f"[WARN] {te}")
            except Exception:
                data.prnt(traceback.format_exc())
            return check_result.gen(query, deezer_result, music_type=music_type)

class data_check:
    def length(source_length, result_length):
        if(not settings.settings.no_length):
            difference = abs(result_length - source_length)
            if(difference > constants.length_difference_threshold):
                return 0.0
            return (1.0-(difference/constants.length_difference_threshold))*constants.length_weight
        else:
            return 0.0