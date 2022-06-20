class submitter:
    os = ""
    version = ""
    int_version = 0
    author = ""
    appname = ""
    ip_address = ""

    def __init__(self, os="", version="", int_version=0, author="", appname="", ip_address=""):
        self.os = os
        self.version = version
        self.int_version = int_version
        self.author = author
        self.appname = appname
        self.ip_address = ip_address

class music:
    name = ""
    title = ""
    description = ""
    id = ""
    bpm = 0
    length = 0
    link = ""
    filename = ""
    isrc = ""
    remix = False

    def __init__(self, name="", title="", description="", id="", bpm=0, length=0, link="", filename="", isrc="", remix=False):
        self.name = name
        self.title = title
        self.description = description
        self.id = id
        self.bpm = bpm
        self.length = length
        self.link = link
        self.filename = filename
        self.isrc = isrc
        self.remix = remix

    class type:
        ONLINE = -1
        DEFAULT = 0
        MIX_OR_ALBUM = 1
        REMIX_OR_COVER_OR_INSTRUMENTAL = 2