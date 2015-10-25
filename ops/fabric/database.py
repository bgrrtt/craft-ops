import fabric.api as fab


@fab.task(default=True)
@fab.hosts()
def database(method='sync', role='web', stage='production', direction='down'):
    state = get_state()

    if (not role) or (role == 'dev'):

        env.hosts = ["localhost"]
        env.host = ["localhost"]
        env.host_string = ["localhost"]

        env.user = state.dev.user

        stage = state.web.stages[stage]
        pprintpp.pprint(stage)

        if method == "import":
            local("mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < ops/database.sql")

        if method == "dump":
            local("mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > ops/database.sql")

        if method == "sync":
            run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
            get("/home/"+stage.user+"/tmp/dump.sql","/tmp/dump.sql")
            local("cd /tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < dump.sql")

    elif role == 'web':
        state = get_state()

        server = state.services.public_ips.web.address

        env.user = state.web.admin.user
        env.hosts = [server]
        env.host = server
        env.host_string = server

        stage = state.web.stages[stage]

        env.user = stage.user

        if method == "down":
            get("/home/"+stage.user+"/tmp/dump.sql","ops/database.sql")

        if method == "up":
            put("ops/database.sql","/home/"+stage.user+"/tmp/import.sql")

        if method == "import":
            run("cd $HOME/tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < import.sql")

        if method == "dump":
            run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
