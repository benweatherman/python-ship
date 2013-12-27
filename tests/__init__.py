import os, tempfile
import ups

def _show_file(extension, data):
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as temp_file:
        temp_file.write(data)
        os.system('open %s' % temp_file.name)

