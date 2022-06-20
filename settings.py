import os

import objects

settings = []

output_dir = ""
working_dir = ""
temp_dir = ".temp/"

logger = None

info_logger = None
download_logger = None

srv_version = ""
submitter_obj = objects.submitter()

# Create fallback temp dir
if(not os.path.exists(temp_dir)):
    os.mkdir(temp_dir)