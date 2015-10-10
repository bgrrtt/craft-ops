from fabric.api import *
from fabric.contrib.project import rsync_project
from bunch import bunchify
from requests.auth import HTTPBasicAuth

import base64
import boto.vpc
import boto.ec2
import boto.ec2.elb
import boto.rds2
import copy
import datetime
import json
import os
import pprintpp
import random
import requests
import ruamel.yaml
import socket
import string
import sys
import time
import urllib
import yaml


@task
def dev():
    state = get_state()

    env.hosts = ["localhost"]
    env.host = ["localhost"]
    env.host_string = ["localhost"]
    env.stages = [state.dev]


@task
def web():
    state = get_state()

    server = state.services.public_ips.web.address

    env.user = state.web.admin.user
    env.hosts = [server]
    env.host = server
    env.host_string = server
    env.key_filename = 'salt/root/web/files/admin.pem'


@task
def production():
    state = get_state()

    server = state.services.public_ips.web.address

    env.forward_agent = True
    env.stages = ['production']
    env.hosts = [server]
    env.host = server
    env.host_string = server


@task
def staging():
    state = get_state()

    server = state.services.public_ips.web.address

    env.forward_agent = True
    env.stages = ['staging']
    env.hosts = [server]
    env.host = server
    env.host_string = server


@task
def preview():
    state = get_state()

    server = state.services.public_ips.web.address

    env.forward_agent = True
    env.stages = ['preview']
    env.hosts = [server]
    env.host = server
    env.host_string = server


@task
def all():
    state = get_state()

    server = state.services.public_ips.web.address

    env.forward_agent = True
    env.stages = ['production','staging','preview']
    env.hosts = [server]
    env.host = server
    env.host_string = server


@task
@hosts()
def check():
    state = get_state(bunch=False)

    pprintpp.pprint(state)


@task
@hosts()
def deploy(branch="master"):
    state = get_state()

    time = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%S%z")

    for current_stage in env.stages:
        stage = state.web.stages[current_stage]
        env.user = stage.user

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


@task
@hosts()
def uploads(method):
    state = get_state()

    for current_stage in env.stages:
        stage = state.web.stages[current_stage]
        env.user = stage.user

        if method == "up":
            local("rsync -avz --progress "+os.environ['UPLOADS_PATH']+"/ "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets")
        if method == "down":
            local("rsync -avz --progress "+env.user+"@"+env.host_string+":/home/"+env.user+"/shared/assets/ "+os.environ['UPLOADS_PATH'])


@task
@hosts()
def db(method):
    state = get_state()

    for current_stage in env.stages:
        if isinstance(current_stage, basestring):
            stage = state.web.stages[current_stage]
        else:
            stage = bunchify(current_stage)

        env.user = stage.user

        if method == "import":
            if env.host == "localhost":
                local("cd /tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < dump.sql")
            else:
                run("cd $HOME/tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < import.sql")
        if method == "dump":
            if env.host == "localhost":
                local("cd /tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
            else:
                run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
        if method == "backup":
            if env.host == "localhost":
                local("mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > salt/root/dev/files/backup.sql")
        if method == "down":
            get("/home/"+stage.user+"/tmp/dump.sql","/tmp/dump.sql")
        if method == "up":
            put("/tmp/dump.sql","/home/"+stage.user+"/tmp/import.sql")
        if method == "sync":
            run("cd $HOME/tmp && mysqldump -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE > dump.sql")
            get("/home/"+stage.user+"/tmp/dump.sql","/tmp/dump.sql")
            local("cd /tmp && mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD $DB_DATABASE < dump.sql")
            


@task
@hosts()
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


@task
@hosts('localhost')
def cleanup(method=False):
    if (not method) or (method == 'database'):
        state = get_state()

        services = state.services

        project, private = yaml_edit("services.database")

        conn = boto.rds2.connect_to_region(services.region)

        if project['services']['database']:
            conn.delete_db_instance(state.name, skip_final_snapshot=True)

            database = conn.describe_db_instances(db_instance_identifier=state.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]

            while database['DBInstanceStatus'] == 'deleting':
                print '...database instance status: %s' % database['DBInstanceStatus']
                time.sleep(10)
                #RDS2 does not offer an "update" method
                try:
                    database = conn.describe_db_instances(db_instance_identifier=state.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]
                except:
                    break

            conn.delete_db_subnet_group(services.database.subnet_group)

            project['services'].pop('database')
            private['services'].pop('database')

            # Clear password and host for each stage
            for name, item in state.web.stages.items():
                private['web']['stages'][name]['envs'].pop('DB_PASSWORD', None)

        yaml_save( { 'project': project, 'private': private } )

    if (not method) or (method == 'web'):
        state = get_state()

        services = state.services

        project, private = yaml_edit("web")

        conn = boto.ec2.connect_to_region(services.region)

        if project['web']['instance_id']:
            conn.terminate_instances([state.web.instance_id])

            instance = conn.get_only_instances(instance_ids=[state.web.instance_id])[0]

            while instance.state == 'shutting-down':
                print '...instance status: %s' % instance.state
                time.sleep(10)
                try:
                    instance.update()
                except:
                    break

            # Attempt to remove IP entry local known_hosts file 
            try:
                local('ssh-keygen -R "'+state.services.public_ips.web.address+'"')
            except:
                pass


        project['web'].pop('vpc_id', None)
        project['web'].pop('subnet_id', None)
        project['web'].pop('placement', None)
        project['web'].pop('instance_id', None)
        project['web'].pop('address_association_id', None)
        project['web'].pop('private_ip_address', None)

        yaml_save( { 'project': project, 'private': private } )

    if (not method) or (method == 'services'):
        state = get_state()

        services = state.services

        project, private = yaml_edit("services")

        conn = boto.vpc.connect_to_region(services.region)

        for name, item in services.key_pairs.items():
            conn.delete_key_pair(name+'-'+state.name)
            local('rm -f '+item.private)
            local('rm -f '+item.public)

        if project['services']['public_ips']:
            for public_ip_name, public_ip in services.public_ips.items():
                conn.release_address(allocation_id=public_ip.allocation_id)

            project['services'].pop('public_ips')

        if project['services']['security_groups']:
            for name, item in services.security_groups.items():
                conn.delete_security_group(group_id=item['id'])

            project['services'].pop('security_groups')

        if project['services']['vpc']:
            from collections import OrderedDict
            for zone, item in project['services']['vpc']['subnets'].items():
                conn.delete_subnet(dict(OrderedDict(item))['id'])

            conn.delete_route_table(services.vpc.route_table_id)

            conn.detach_internet_gateway(services.vpc.internet_gateway_id, services.vpc.id)
            conn.delete_internet_gateway(services.vpc.internet_gateway_id)

            conn.delete_vpc(services.vpc.id)

            project['services'].pop('vpc')

        project.pop('services')

        yaml_save( { 'project': project } )

    if (not method) or (method == "git"):
        state = get_state()

        services = state.services

        project, private = yaml_edit("git")

        project_name = state.name
        bitbucket_user = state.dev.envs.BITBUCKET_USER
        bitbucket_token = state.dev.envs.BITBUCKET_PASS_TOKEN
        auth = HTTPBasicAuth(bitbucket_user, bitbucket_token)

        req = requests.get('https://api.bitbucket.org/2.0/repositories/'+bitbucket_user+'/'+project_name, auth=auth)

        if req.status_code == 200:
            data = { 'owner': bitbucket_user, 'repo_slug': project_name }
            req = requests.delete('https://api.bitbucket.org/1.0/repositories/'+bitbucket_user+'/'+project_name, data=data, auth=auth)

            if req.status_code == 204:
                project.pop('git')

        yaml_save( { 'project': project } )

    if (not method) or (method == 'dev'):
        state = get_state()

        project, private = yaml_edit("dev")

        key_pair = state.services.key_pairs.dev

        local('rm -f '+key_pair.private)
        local('rm -f '+key_pair.public)

        project['web']['deploy_keys'].pop('dev')

        yaml_save( { 'project': project, 'private': private } )
            

@task
@hosts('localhost')
def setup(method=False):

    project, private = get_input()
    yaml_save( { 'project': project, 'private': private } )

    if (not method) or (method == 'dev'):
        state = get_state()

        project, private = yaml_edit("web")

        key_pair = state.services.key_pairs.dev

        local("openssl genrsa -out "+key_pair.private+" 2048")
        local("chmod 600 "+key_pair.private)
        local("ssh-keygen -f "+key_pair.private+" -y > "+key_pair.public)

        public_key_data = local("cat " + key_pair.public, capture=True)

        if 'web' not in project:
            project['web'] = {}
        if 'deploy_keys' not in project['web']:
            project['web']['deploy_keys'] = {}

        project['web']['deploy_keys']['dev'] = str(public_key_data)

        yaml_save( { 'project': project, 'private': private } )

    if (not method) or (method == 'services'):
        state = get_state()

        services = state.services
        
        project, private = yaml_edit("services")

        conn = boto.vpc.connect_to_region(services.region)

        if 'vpc' not in project['services']:

            project['services']['vpc'] = {}

            vpc = conn.create_vpc(services.vpc.cidr_block)
            project['services']['vpc']['id'] = vpc.id

            conn.modify_vpc_attribute(vpc.id, enable_dns_support=True)
            conn.modify_vpc_attribute(vpc.id, enable_dns_hostnames=True)

            internet_gateway = conn.create_internet_gateway()
            project['services']['vpc']['internet_gateway_id'] = internet_gateway.id

            conn.attach_internet_gateway(internet_gateway.id, vpc.id)

            route_table = conn.create_route_table(vpc.id)
            project['services']['vpc']['route_table_id'] = route_table.id

            conn.create_route(route_table.id, '0.0.0.0/0', internet_gateway.id)

            subnets = {}
            for zone, item in services.vpc.subnets.items():
                try:
                    subnet = conn.create_subnet(
                        vpc.id,
                        item.cidr_block,
                        availability_zone=zone

                    )

                    subnets[zone] = {
                        'id': subnet.id
                    }

                    conn.associate_route_table(route_table.id, subnet.id)
                except:
                    pass

            project['services']['vpc']['subnets'] = subnets

        for key_name, key in state.services.key_pairs.items():
            if not os.path.isfile(key.private): 
                # Make new key pair
                local("openssl genrsa -out "+key.private+" 2048")
                local("chmod 600 "+key.private)
                local("ssh-keygen -f "+key.private+" -y > "+key.public)

                with open(key.public) as public_key:
                    conn.import_key_pair(key_name+'-'+state.name, public_key.read())

        if 'security_groups' not in project['services']:
            project['services']['security_groups'] = {}

            security_groups = {}
            for name, item in state.services.security_groups.items():
                # Make a new security group
                security_group = conn.create_security_group(
                    name+'-'+state.name,
                    item.description,
                    vpc_id=vpc.id
                )

                for rule in item.rules:
                    security_group.authorize('tcp', rule.port, rule.port, rule.source)

                security_groups[name] = {
                    'id': security_group.id
                }

                project['services']['security_groups'] = security_groups

        if 'public_ips' not in project['services']:
            project['services']['public_ips'] = {}

            public_ips = state.services.public_ips
            for ip_name, ip in public_ips.items():
                # Make a new pulic ip
                address = conn.allocate_address(domain='vpc')
                project['services']['public_ips'][ip_name] = {
                    'address': address.public_ip,
                    'allocation_id': address.allocation_id
                }

        yaml_save( { 'project': project } )

    if (not method) or (method == 'database'):
        state = get_state()

        services = state.services

        conn = boto.rds2.connect_to_region(services.region)

        project, private = yaml_edit("services.database")

        if not project['services']['database']:

            subnet_ids = []
            for zone, subnet in project['services']['vpc']['subnets'].items():
                subnet_ids.append(subnet['id'])    

            conn.create_db_subnet_group(
                state.name,
                'Default db subnet group.',
                subnet_ids
            )

            admin_username = services.database.username if services.database.username else 'admin'
            admin_password = services.database.password if services.database.password else random_generator()

            conn.create_db_instance(
                state.name,
                services.database.size,
                services.database.instance_class,
                services.database.engine,
                admin_username,
                admin_password,
                db_subnet_group_name=state.name,
                vpc_security_group_ids=[services.security_groups.database.id]
            )

            database = conn.describe_db_instances(db_instance_identifier=state.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]

            while database['DBInstanceStatus'] != 'available':
                print '...database instance status: %s' % database['DBInstanceStatus']
                time.sleep(10)
                #RDS2 does not offer an "update" method
                try:
                    database = conn.describe_db_instances(db_instance_identifier=state.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]
                except:
                    break

            project['services']['database']['host'] = database['Endpoint']['Address']
            project['services']['database']['subnet_group'] = state.name
            project['services']['database']['username'] = admin_username

            private['services']['database']['password'] = admin_password

            # Generate passwords for each stage and add host
            if 'web' not in project:
                project['web'] = {}
            if 'web' not in private:
                private['web'] = {}

            if 'stages' not in project['web']:
                project['web']['stages'] = {}
            if 'stages' not in private['web']:
                private['web']['stages'] = {}

            for name, item in state.web.stages.items():
                if name not in project['web']['stages']:
                    project['web']['stages'][name] = {}
                    project['web']['stages'][name]['envs'] = {}

                if name not in private['web']['stages']:
                    private['web']['stages'][name] = {}
                    private['web']['stages'][name]['envs'] = {}

                private['web']['stages'][name]['envs']['DB_PASSWORD'] = random_generator()

        yaml_save( { 'project': project, 'private': private } )


    if (not method) or (method == 'git'):
        state = get_state()

        project, private = yaml_edit("git")

        auth = HTTPBasicAuth(state.dev.envs.BITBUCKET_USER, state.dev.envs.BITBUCKET_PASS_TOKEN)
        
        ssh_pub_key = local("cat "+state.services.key_pairs.web.public, capture=True)
        repo_url = "git@bitbucket.org:"+state.dev.envs.BITBUCKET_USER+"/"+state.name+".git"

        req = requests.get('https://api.bitbucket.org/2.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.name, auth=auth)
        if req.status_code == 404:
            data = {
                'scm': 'git',
                'owner': state.dev.envs.BITBUCKET_USER,
                'repo_slug': state.name,
                'is_private': True
            }
            req = requests.post('https://api.bitbucket.org/2.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.name, data=data, auth=auth)
            pprintpp.pprint(req.json())

        req = requests.get('https://bitbucket.org/api/1.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.name+'/deploy-keys', auth=auth)
        if req.status_code == 200:
            data = {
                'accountname': state.dev.envs.BITBUCKET_USER,
                'repo_slug': state.name,
                'label': state.name,
                'key': ssh_pub_key
            }
            req = requests.post('https://bitbucket.org/api/1.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.name+'/deploy-keys', data=data, auth=auth)
            pprintpp.pprint(req.json())

        with settings(warn_only=True):
            has_git_dir = local("test -d .git", capture=True)
            if has_git_dir.return_code != "0":
                local("git init")

        git_remotes = local("git remote", capture=True)
        if "origin" not in git_remotes:
            local("git remote add origin "+repo_url)
        else:
            local("git remote set-url origin "+repo_url)

        project['git']['repo'] = repo_url

        yaml_save( { 'project': project } )


    if (not method) or (method == 'web'):
        state = get_state()

        services = state.services
        
        project, private = yaml_edit("web")

        conn = boto.ec2.connect_to_region(services.region)

        project['web']['vpc_id'] = state.services.vpc.id

        subnet_ids = []
        id_to_zone = {}
        for zone, item in services.vpc.subnets.items():
            if item['id'] is not None:
                subnet_ids.append(item['id'])
                id_to_zone[item['id']] = zone

        subnet_id = random.choice(subnet_ids)
        placement = id_to_zone[subnet_id]

        project['web']['subnet_id'] = subnet_id
        project['web']['placement'] = placement

        security_group_ids = []
        for name in state.web.security_groups:
            security_group_ids.append(services.security_groups[name].id)

        if 'instance_id' not in project['web']:
            # Make a new instance
            instance = conn.run_instances(
                state.web.ami_id,
                instance_type=state.web.instance_type,
                key_name=state.web.key_pair+'-'+state.name,
                placement=placement,
                subnet_id=subnet_id,
                security_group_ids=security_group_ids
            ).instances[0]

            while instance.state != 'running':
                print '... waitng for web instance to become ready'
                time.sleep(10)
                instance.update()

            instance = conn.get_only_instances(instance_ids=[instance.id])[0]

            project['web']['instance_id'] = instance.id
            project['web']['private_ip_address'] = instance.private_ip_address

        if 'address_association_id' not in project['web']:
            address_association_id = conn.associate_address_object(
                instance_id=instance.id,
                allocation_id=state.services.public_ips.web.allocation_id
            ).association_id

            project['web']['address_association_id'] = address_association_id

            #Now we need to wait for "Initializing" to finish, let's keep trying to reach the server
            reachable = False
            while not reachable:
                print '... waitng for web instance to become ready'
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    s.connect((state.services.public_ips.web.address, 22))
                    reachable = True
                except:
                    pass
                s.close()

        if 'load_balancer' not in project['web'] and state.web.load_balancer.enabled:
            conn = boto.ec2.elb.connect_to_region(services.region)

            project['web']['load_balancer'] = {}

            security_group_ids = []
            for name in state.web.load_balancer.security_groups:
                security_group_ids.append(services.security_groups[name].id)

            load_balancer = conn.create_load_balancer(
                name=state.name,
                zones=None,
                subnets=subnet_ids,
                listeners=[(80, 80, 'tcp'), (443, 80, 'tcp')],
                security_groups=security_group_ids
            )

            project['web']['load_balancer']['name'] = state.name

            conn.register_instances(
                state.name,
                [instance.id]
            )

        yaml_save( { 'project': project, 'private': private } )

        # Auto-add the host to known_hosts
        local("ssh-keyscan -t rsa "+state.services.public_ips.web.address+" >> ~/.ssh/known_hosts")

        # Provision the newly created instance
        local("fab web provision")


@task
@hosts()
def provision():
    state = get_state()

    if env.host == 'localhost':
        state['role'] = 'dev'
        local("sudo salt-call state.highstate --config-dir='/srv' pillar='"+json.dumps(state)+"' -l debug")
    else:
        user = state.web.admin.user
        group = state.web.admin.group

        # Get the files where they need to be before provisioning
        sudo("mkdir -p /srv")
        sudo("chown -R "+user+":"+group+" /srv")
        rsync_project("/srv/", "./salt/", exclude=["*admin.pem","*dev.pem"])

        with settings(warn_only=True):
            check_for_salt = run("which salt-call")
            if check_for_salt.return_code != 0:
                # Install Salt
                run("cd /tmp && wget https://github.com/saltstack/salt-bootstrap/archive/v2015.08.06.tar.gz -q")

                md5 = run("cd /tmp && md5sum v2015.08.06.tar.gz | awk '{ print $1 }'").strip()
                if md5 != "60110888b0af976640259dea5f9b6727":
                    sys.exit()

                run("cd /tmp && tar -xvf v2015.08.06.tar.gz")
                run("cd /tmp && sudo sh salt-bootstrap-2015.08.06/bootstrap-salt.sh -P -p python-dev -p python-pip -p python-git -p unzip")

        # Provision the machine
        state['role'] = 'web'
        sudo("salt-call state.highstate --config-dir='/srv' pillar='"+json.dumps(state)+"' -l debug")


@task
def find(query=""):
    local("ack "+query+" --ignore-dir=craft/plugins --ignore-dir=craft/storage --ignore-dir=.vagrant --ignore-dir=vendor --ignore-dir=.git")


@task
def tree():
    local("tree -a -I 'vendor|.git|storage|plugins|.vagrant'")


@task
def ssh():
    state = get_state()

    local("ssh -i salt/root/web/files/admin.pem "+state.web.admin.user+"@"+state.services.public_ips.web.address)


@task
def craft(method=False):
    state = get_state()

    if (not method) or (method == 'install'):
        plugins = state.craft.plugins
        plugin_names = []

        for name, item in plugins.items():
            plugin_names.append(name)

        email = urllib.quote_plus(state.craft.email)
        username = urllib.quote_plus(state.craft.username)
        password =  urllib.quote_plus(state.craft.password)
        siteName = urllib.quote_plus(state.name)
        server_name = urllib.quote_plus(state.web.server_name)

        local("curl 'http://localhost:8000/index.php?p=admin/actions/install/install' -H 'X-Requested-With: XMLHttpRequest' --data 'username="+username+"&email="+email+"&password="+password+"&siteName="+siteName+"&siteUrl=http%3A%2F%2F"+server_name+"&locale=en_us' --compressed")


    if (not method) or (method == 'plugins'):
        plugins = state.craft.plugins
        plugin_names = []

        for name, item in plugins.items():
            plugin_names.append(name)

        local("curl http://localhost:8000/plugins.php?plugins="+urllib.quote_plus(json.dumps(plugin_names)))


def dict_merge(a, b):
    '''recursively merges dict's. not just simple a['key'] = b['key'], if
    both a and bhave a key who's value is a dict then dict_merge is called
    on both values and the result stored in the returned dictionary.'''
    if not isinstance(b, dict):
        return b
    result = copy.deepcopy(a)
    for k, v in b.iteritems():
        if k in result and isinstance(result[k], dict):
                result[k] = dict_merge(result[k], v)
        else:
            result[k] = copy.deepcopy(v)
    return result


def get_state(bunch=True):
    with open('defaults.conf') as defaults_file:
        defaults_file_content = defaults_file.read()

    state = yaml.load(defaults_file_content)

    if os.path.isfile('project.conf'):
        with open('project.conf') as project_file:
            project_file_content = project_file.read()
        project = yaml.load(project_file_content)
        state = dict_merge(state, project)

    if os.path.isfile(os.environ['HOME']+'/ops.conf'):
        with open(os.environ['HOME']+'/ops.conf') as ops_file:
            ops_file_content = ops_file.read()
        ops = yaml.load(ops_file_content)
        state = dict_merge(state, ops)

    if os.path.isfile('private.conf'):
        with open('private.conf') as private_file:
            private_file_content = private_file.read()
        private = yaml.load(private_file_content)
        state = dict_merge(state, private)

    if bunch:
        return bunchify(state)
    else:
        return state


def yaml_edit(tree):
    files = { "project": {}, "private": {} }

    tree = tree.split('.')

    for name, item in files.items():
        if os.path.isfile(name+'.conf'): 
            with open(name+'.conf') as opened_file:
                file_content = opened_file.read()
        else:
            file_content = tree[0]+": null"

        files[name] = ruamel.yaml.load(file_content, ruamel.yaml.RoundTripLoader)

        for index, value in enumerate(tree):
            if index == 0:
                if value not in files[name] or not files[name][value]:
                    files[name][value] = {}

            if index >= 1:
                if value not in files[name][tree[0]]:
                    files[name][tree[0]][value] = {}

            if index >= 2:
                if value not in files[name][tree[0]][tree[1]]:
                    files[name][tree[0]][tree[1]][value] = {}

    return files['project'], files['private']


def get_input():
    files = { "project": {}, "private": {} }

    for name, item in files.items():
        if os.path.isfile(name+'.conf'): 
            with open(name+'.conf') as opened_file:
                file_content = opened_file.read()

            files[name] = ruamel.yaml.load(file_content, ruamel.yaml.RoundTripLoader)

        if type(files[name]) is not dict and type(files[name]) is not ruamel.yaml.comments.CommentedMap:
            files[name] = {}

        if name == 'project':
            if 'name' not in files[name]:
                files[name]['name'] = raw_input("Enter a computer safe name for the project:")

            if 'craft' not in files[name]:
                files[name]['craft'] = {}

            if 'username' not in files[name]['craft']:
                files[name]['craft']['username'] = raw_input("Enter a username for the craft user:")

            if 'email' not in files[name]['craft']:
                files[name]['craft']['email'] = raw_input("Enter an email address for the craft user:")

            if 'web' not in files[name]:
                files[name]['web'] = {}

            if 'server_name' not in files[name]['web']:
                files[name]['web']['server_name'] = raw_input("Enter the project domain name:")

        if name == 'private':
            if 'craft' not in files[name]:
                files[name]['craft'] = {}

            if 'password' not in files[name]['craft']:
                files[name]['craft']['password'] = raw_input("Enter a password for the craft user:")

    return files['project'], files['private']


def yaml_save(objects):
    for name, item in objects.items():
        item = remove_empty(item)
        
        if item:
            with open(name+'.conf', 'w+') as outfile:
                outfile.write( ruamel.yaml.dump(item, Dumper=ruamel.yaml.RoundTripDumper) )
        else:
            try:
                os.remove(name+'.conf')
            except:
                pass


def random_generator(size=16, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for x in range(size))


def remove_empty(yaml):
    for name, item in yaml.items():
        if type(item) is dict or type(item) is ruamel.yaml.comments.CommentedMap:
            remove_empty(item)
        if not item and item != 0 and item != False:
            yaml.pop(name)
    return yaml
