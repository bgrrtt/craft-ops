import fabric.api as fab


@fab.task(default=True)
@fab.hosts()
def uploads(method='sync', role='web', stage='production', direction='down'):

    state = get_state()

    stage = state.web.stages[stage]

    server = state.services.public_ips.web.address

    env.user = stage.user

    env.forward_agent = True
    env.hosts = [server]
    env.host = server
    env.host_string = server

    if direction == "down":
        local("rsync -avz --progress "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets/ "+os.environ['UPLOADS_PATH'])
    if direction == "up":
        local("rsync -avz --progress "+os.environ['UPLOADS_PATH']+"/ "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets")
