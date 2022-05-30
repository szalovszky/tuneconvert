import sys
import asyncio

from utils import data
from platforms import *
import constants
from timeout import timeout

class check_result:
    id = ""
    score = 1.0
    result = None

    def __init__(self, id="", score=1.0, result=None):
        self.id = id
        self.score = score
        self.result = result

    def gen(query, result):
        result_check = deezer_platform.check_result(query=query, result=result)
        if(result_check is not None):
            if(not result_check):
                return None
        return result if result is None else check_result(id=data.hash(str(result_check)), score=1, result=result_check).__dict__

class deezer_check:
    def track(query):
        if(not settings.settings.no_deezertrack):
            deezer_result = deezer_platform.search_track(query)
            return check_result.gen(query, deezer_result)
    
    def album(query):
        if(not settings.settings.no_deezeralbum):
            try:
                iterator = iter(query)
            except TypeError:
                pass
            else:
                query = " ".join(query)
            deezer_result = deezer_platform.search_album(query)
            return check_result.gen(query, deezer_result)

class startpage_check:
    def search(query):
        if(not settings.settings.no_startpage):
            deezer_result = None
            startpage_result = startpage_platform.search_track(query, use_spotify=False)
            if(startpage_result is not None):
                deezer_result = deezer_platform.tracklink(startpage_result)
            return check_result.gen(query, deezer_result)

class duckduckgo_check:
    def search(query):
        if(settings.settings.experimental_ddg):
            deezer_result = None
            ddg_result = ddg_platform.search_track(query, use_spotify=False)
            if(ddg_result is not None):
                deezer_result = deezer_platform.tracklink(ddg_result)
            return check_result.gen(query, deezer_result)

loop = asyncio.get_event_loop()

class shazam_check:
    def search(query, filename):
        global loop
        if(not settings.settings.no_shazam):
            deezer_result = None
            shazam = loop.run_until_complete(shazam_platform.recognize(filename))
            if(shazam is not None):
                deezer_result = deezer_platform.isrc(shazam)
            return check_result.gen(query, deezer_result)

class external_check:
    def links(query, description):
        if(not settings.settings.no_links):
            deezer_result = None
            links = music_data.check_links(description.replace("\n", " "))
            if(links is not None):
                if(links[0] is not None):
                    id = links[0]
                    deezer_result = deezer_platform.trackid(id)
                elif(lres[1] is not None):
                    isrc = links[1]
                    deezer_result = deezer_platform.isrc(isrc)
            return check_result.gen(query, deezer_result)