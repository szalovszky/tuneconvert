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
    type = 0

    def __init__(self, name="", title="", description="", id="", bpm=0, length=0, link="", filename="", isrc="", type=0):
        self.name = name
        self.title = title
        self.description = description
        self.id = id
        self.bpm = bpm
        self.length = length
        self.link = link
        self.filename = filename
        self.isrc = isrc
        self.type = type

    class type:
        ONLINE = -1
        DEFAULT = 0
        MIX_OR_ALBUM = 1
        REMIX_OR_COVER_OR_INSTRUMENTAL = 2

        list = {DEFAULT: "DEFAULT", MIX_OR_ALBUM: "MIX_OR_ALBUM", REMIX_OR_COVER_OR_INSTRUMENTAL: "REMIX_OR_COVER_OR_INSTRUMENTAL", ONLINE: "ONLINE"}