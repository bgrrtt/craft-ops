import os

from fabric.api import *
from pprintpp import pprint as out
from utils import *

# Importing fabric tasks...
import setup
import cleanup
import provision
import deploy
import database as db
import uploads
import craft
 

state = get_state()

os.environ["AWS_ACCESS_KEY_ID"] = state.dev.envs.AWS_ACCESS_KEY
os.environ["AWS_SECRET_ACCESS_KEY"] = state.dev.envs.AWS_SECRET_KEY


@task
@hosts()
def check():
    state = get_state(bunch=False)
    out(state)


@task
def find(query=""):
    local("ack "+query+" --ignore-dir=craft/plugins --ignore-dir=craft/storage --ignore-dir=.vagrant --ignore-dir=vendor --ignore-dir=.git")


@task
def tree():
    local("tree -a -I 'vendor|.git|storage|plugins|.vagrant'")


@task
def ssh():
    state = get_state()

    local("ssh -i ops/keys/admin.pem "+state.web.admin.user+"@"+state.services.public_ips.web.address)
