import deezer

class deezer_platform:
    def search_track(query):
        success = False
        while(not success):
            try:
                res = deezerc.search(query)
                if(len(res) <= 0):
                    res = None
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    res = None
                    break
        return res

    def isrc(isrc):
        success = False
        while(not success):
            try:
                res = deezerc.request("GET", "track/isrc:" + isrc, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    res = None
                    break
        return res

    def trackid(id):
        success = False
        while(not success):
            try:
                res = deezerc.request("GET", "track/" + id, resource_type=deezer.Track)
                success = True
            except Exception as e:
                if("quota" in str(e).lower()):
                    time.sleep(1)
                else:
                    res = None
                    break
        return res

    def search_album(query):
        success = False
        while(not success):
            try:
                res = deezerc.request("GET", "search/album?q=" + query, resource_type=deezer.Album)
                if(len(res) > 0):
                    res = res[0].as_dict()
                    if(res['record_type'] == "single"):
                        res = deezerc.request("GET", res['tracklist'].replace("https://api.deezer.com/", ""))
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
                    res = None
                    break
        return res