import fabric.api as fab


@fab.task(default=True)
@fab.hosts()
def deploy(stage='staging', branch="master"):

    state = get_state()

    stage = state.web.stages[stage]

    server = state.services.public_ips.web.address

    env.user = stage.user

    env.forward_agent = True
    env.hosts = [server]
    env.host = server
    env.host_string = server

    time = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%z")

    run("cd $HOME/source && git fetch origin "+branch)
    run("cd $HOME/source && git archive origin/"+branch+" --prefix=$HOME/releases/"+time+"/ | (cd /; tar xf -)")

    run("rm -rf $HOME/current")

    run("ln -s $HOME/releases/"+time+" $HOME/current")

    run("ln -s $HOME/shared/vendor $HOME/current/vendor")
    run("ln -s $HOME/shared/assets $HOME/current/public/assets")

    run("rm -rf $CRAFT_PATH/config")
    run("ln -s $HOME/current/craft/config $CRAFT_PATH/config")

    if state.craft.translations:
        run("rm -rf $CRAFT_PATH/translations")
        run("ln -s $HOME/current/craft/translations $CRAFT_PATH/translations")

    run("rm -rf $CRAFT_PATH/templates")
    run("ln -s $HOME/current/templates $CRAFT_PATH/templates")

    run("rm -rf $CRAFT_PATH/plugins")
    run("ln -s $HOME/shared/plugins $CRAFT_PATH/plugins")

    run("rm -rf $CRAFT_PATH/storage")
    run("ln -s $HOME/shared/storage $CRAFT_PATH/storage")

    run("ln -s $HOME/shared/static $HOME/current/public/static")
    run("cd $HOME/current && harp compile assets public/static")

    run("ln -s $HOME/shared/bower_components $HOME/current/public/static/vendor")
    run("cd $HOME/current && bower install")


@fab.task
@fab.hosts()
def releases(method="clean"):
    state = get_state()

    if method == "clean":
        for current_stage in env.stages:
            stage = state.web.stages[current_stage]
            env.user = stage.user

            output = run("ls $HOME/releases")
            releases = sorted(output.split(), reverse=True)
            keep = 3

            for index, release in enumerate(releases):
                if keep <= index:
                    print "removing =>"
                    print release
                    run("rm -rf $HOME/releases/"+release)
                else:
                    print "keeping =>"
                    print release

