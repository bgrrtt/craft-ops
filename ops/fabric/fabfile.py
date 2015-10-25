from fabric.api import *
from pprintpp import pprint as out
from utils import *

# Importing tasks...
import setup
import cleanup
import provision
import deploy
import database as db
import uploads


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
