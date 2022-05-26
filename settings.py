import os

settings = []

output_dir = ""
working_dir = ""
temp_dir = ".temp/"

logger = None

# Create fallback temp dir
if(not os.path.exists(temp_dir)):
    os.mkdir(temp_dir)