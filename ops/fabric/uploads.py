from fabric.api import *
from pprintpp import pprint as out
from requests.auth import HTTPBasicAuth
from utils import *


@task(default=True)
@hosts()
def uploads(method=False, role='dev', stage=False, direction='down'):

    env.forward_agent = True

    state = get_state()

    if method == "sync":
        if stage:
            stage = set_stage(stage)
        else:
            stage = set_stage('production')

        set_env('web', stage)

        if direction == "down":
            local("rsync -avz --progress "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets/ "+os.environ['UPLOADS_PATH'])
        if direction == "up":
            local("rsync -avz --progress "+os.environ['UPLOADS_PATH']+"/ "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets")
