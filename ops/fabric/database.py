from fabric.api import *
from pprintpp import pprint as out
from requests.auth import HTTPBasicAuth
from utils import *


@task(default=True)
@hosts()
def database(method=False, role='dev', stage=False, direction='down'):
    state = get_state()

    env.forward_agent = True

    if method == "sync":
        if stage:
            stage = set_stage(stage)
        else:
            stage = set_stage('production')

        set_env('web', stage)

        if direction == 'down':
            run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
            get("/home/"+stage.user+"/tmp/dump.sql","ops/database.sql")
            local("mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < ops/database.sql")
        
        if direction == 'up':
            local("mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > ops/database.sql")
            put("ops/database.sql","/home/"+stage.user+"/tmp/import.sql")
            run("cd $HOME/tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < import.sql")

    if method == "import":
        if role == 'dev' and not stage:
            set_env('dev')

            local("mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < ops/database.sql")

        if stage:
            stage = set_stage(stage)

            set_env('web', stage)

            run("cd $HOME/tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < import.sql")

    if method == "dump":
        if role == 'dev' and not stage:
            set_env('dev')

            local("mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > ops/database.sql")

        if stage:
            stage = set_stage(stage)

            set_env('web', stage)

            run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")

    if method == "down":
        if stage:
            stage = set_stage(stage)
        else:
            stage = set_stage('production')

        set_env('web', stage)

        get("/home/"+stage.user+"/tmp/dump.sql","ops/database.sql")

    if method == "up":
        if stage:
            stage = set_stage(stage)
        else:
            stage = set_stage('staging')

        set_env('web', stage)

        put("ops/database.sql","/home/"+stage.user+"/tmp/import.sql")

