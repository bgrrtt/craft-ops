import hashlib
import requests

from fabric.api import *
from pprintpp import pprint as out
from requests.auth import HTTPBasicAuth
from utils import *


@task(default=True)
@hosts()
def craft(method=False, role='dev', stage=False):
    state = get_state()

    env.forward_agent = True

    if method == "update":
        project, private = yaml_edit(['craft'])

        r = requests.get('https://api.github.com/repos/pixelandtonic/Craft-Release/commits')
        packageCommit = r.json()[0]['sha']
        packageUrl = "https://github.com/pixelandtonic/Craft-Release/archive/"+packageCommit+".tar.gz"
        localPackage = download_file(packageUrl)
        packageHash = get_hash(localPackage)

        project['craft']['ref'] = packageCommit
        project['craft']['md5'] = packageHash

        out(project)

        yaml_save( { 'project': project, 'private': private } )


def download_file(url):
    local_filename = '/tmp/' + url.split('/')[-1]
    # NOTE the stream=True parameter
    r = requests.get(url, stream=True)
    with open(local_filename, 'wb') as f:
        for chunk in r.iter_content(chunk_size=1024): 
            if chunk: # filter out keep-alive new chunks
                f.write(chunk)
                #f.flush() commented by recommendation from J.F.Sebastian
    return local_filename


def get_hash(filename):
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    with open(filename, 'rb') as afile:
        buf = afile.read(BLOCKSIZE)
        while len(buf) > 0:
            hasher.update(buf)
            buf = afile.read(BLOCKSIZE)
    return hasher.hexdigest()
