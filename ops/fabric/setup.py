import boto.vpc
import boto.ec2
import boto.ec2.elb
import boto.rds2
import json
import requests
import socket
import time
import urllib

from fabric.api import *
from pprintpp import pprint as out
from requests.auth import HTTPBasicAuth
from utils import *


@task(default=True)
@hosts()
def setup(method=False):

    state = get_state()
    if (not method) or (method == 'input') and 'input' not in state.setup:

        project, private = yaml_edit([
            'setup[]',
            'project',
            'craft',
            'web.stages.preview.envs',
            'web.stages.staging.envs',
            'web.stages.production.envs',
            'dev.envs',
            'database'
        ])

        if not state.project.name:
            project['project']['name'] = raw_input("Enter a computer safe name for the project:")

        if not state.craft.username:
            project['craft']['username'] = raw_input("Enter a username for the craft user:")

        if not state.craft.password:
            password = raw_input("Enter a admin admin password (leave empty to have one generated):")
            if not password:
                password = random_generator()

            private['craft']['password'] = password

        if not state.craft.email:
            project['craft']['email'] = raw_input("Enter an email address for the craft user:")

        if not state.web.server_name:
            project['web']['server_name'] = raw_input("Enter the project domain name:")

        if not state.dev.envs.BITBUCKET_USER:
            private['dev']['envs']['BITBUCKET_USER'] = raw_input("Enter bitbucket team name:")

        if not state.dev.envs.BITBUCKET_PASS_TOKEN:
            private['dev']['envs']['BITBUCKET_PASS_TOKEN'] = raw_input("Enter bitbucket team access token:")

        if not state.dev.envs.AWS_ACCESS_KEY:
            private['dev']['envs']['AWS_ACCESS_KEY'] = raw_input("Enter aws iam admin access key:")

        if not state.dev.envs.AWS_SECRET_KEY:
            private['dev']['envs']['AWS_SECRET_KEY'] = raw_input("Enter aws iam admin secret key:")

        if not state.database.username:
            project['database']['username'] = raw_input("Enter a database admin username:")

        if not state.database.password:
            password = raw_input("Enter a database admin password (leave empty to have one generated):")
            if not password:
                password = random_generator()

            private['database']['password'] = password

        for name, stage in state.web.stages.items():
            if not stage.envs.DB_PASSWORD:
                password = raw_input("Enter a password for the web '"+name+"' DB user (leave empty to have one generated):")
                if not password:
                    password = random_generator()

                private['web']['stages'][name]['envs']['DB_PASSWORD'] = password

        yaml_save( { 'project': project, 'private': private } )


    state = get_state()
    if (not method or method == 'craft') and ('craft' not in state.setup):

        project, private = yaml_edit(['setup[]'])

        project['setup'].append('craft')

        plugins = state.craft.plugins
        plugin_names = []

        for name, item in plugins.items():
            plugin_names.append(name)

        email = urllib.quote_plus(state.craft.email)
        username = urllib.quote_plus(state.craft.username)
        password =  urllib.quote_plus(state.craft.password)
        siteName = urllib.quote_plus(state.project.name)
        server_name = urllib.quote_plus(state.web.server_name)

        local("curl 'http://localhost:8000/index.php?p=admin/actions/install/install' -H 'X-Requested-With: XMLHttpRequest' --data 'username="+username+"&email="+email+"&password="+password+"&siteName="+siteName+"&siteUrl=http%3A%2F%2F"+server_name+"&locale=en_us' --compressed")

        plugins = state.craft.plugins
        plugin_names = []

        for name, item in plugins.items():
            plugin_names.append(name)

        local("curl http://localhost:8000/plugins.php?plugins="+urllib.quote_plus(json.dumps(plugin_names)))

        yaml_save( { 'project': project, 'private': private } )

    state = get_state()
    if (not method or method == 'dev') and ('dev' not in state.setup):

        project, private = yaml_edit(['setup[]', 'web.deploy_keys'])

        project['setup'].append('dev')

        local("openssl genrsa -out ops/keys/dev.pem 2048")
        local("chmod 600 ops/keys/dev.pem")
        local("ssh-keygen -f ops/keys/dev.pem -y > ops/keys/dev.pub")

        public_key_data = local("cat ops/keys/dev.pub", capture=True)

        project['web']['deploy_keys']['dev'] = str(public_key_data)

        yaml_save( { 'project': project, 'private': private } )

    state = get_state()
    if (not method or method == 'services') and ('services' not in state.setup):

        project, private = yaml_edit([
            'setup[]',
            'services.vpc',
            'services.security_groups',
            'services.public_ips'
        ])

        project['setup'].append('services')

        services = state.services

        conn = boto.vpc.connect_to_region(services.region)

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
                    conn.import_key_pair(key_name+'-'+state.project.name, public_key.read())

        security_groups = {}
        for name, item in state.services.security_groups.items():
            # Make a new security group
            security_group = conn.create_security_group(
                name+'-'+state.project.name,
                item.description,
                vpc_id=vpc.id
            )

            for rule in item.rules:
                security_group.authorize('tcp', rule.port, rule.port, rule.source)

            security_groups[name] = {
                'id': security_group.id
            }

            project['services']['security_groups'] = security_groups

        public_ips = state.services.public_ips
        for ip_name, ip in public_ips.items():
            # Make a new pulic ip
            address = conn.allocate_address(domain='vpc')
            project['services']['public_ips'][ip_name] = {
                'address': address.public_ip,
                'allocation_id': address.allocation_id
            }

        yaml_save( { 'project': project } )

    state = get_state()
    if (not method or method == 'database') and ('database' not in state.setup):

        project, private = yaml_edit(['setup[]', 'database', 'web.stages'])

        project['setup'].append('database')

        conn = boto.rds2.connect_to_region(state.services.region)

        database = state.database

        subnet_ids = []
        for zone, subnet in project['services']['vpc']['subnets'].items():
            subnet_ids.append(subnet['id'])    

        conn.create_db_subnet_group(
            state.project.name,
            'Default db subnet group.',
            subnet_ids
        )

        admin_username = database.username
        admin_password = database.password

        conn.create_db_instance(
            state.project.name,
            database.size,
            database.instance_class,
            database.engine,
            admin_username,
            admin_password,
            db_subnet_group_name=state.project.name,
            vpc_security_group_ids=[state.services.security_groups.database.id]
        )

        database = conn.describe_db_instances(db_instance_identifier=state.project.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]

        while database['DBInstanceStatus'] != 'available':
            print '...database instance status: %s' % database['DBInstanceStatus']
            time.sleep(10)
            #RDS2 does not offer an "update" method
            try:
                database = conn.describe_db_instances(db_instance_identifier=state.project.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]
            except:
                break

        project['database']['host'] = database['Endpoint']['Address']
        project['database']['subnet_group'] = state.project.name
        project['database']['username'] = admin_username

        private['database']['password'] = admin_password

        for name, item in state.web.stages.items():
            if name not in project['web']['stages']:
                project['web']['stages'][name] = {}
                project['web']['stages'][name]['envs'] = {}

            if name not in private['web']['stages']:
                private['web']['stages'][name] = {}
                private['web']['stages'][name]['envs'] = {}

            private['web']['stages'][name]['envs']['DB_PASSWORD'] = random_generator()

        yaml_save( { 'project': project, 'private': private } )


    state = get_state()
    if (not method or method == 'git') and ('git' not in state.setup):

        project, private = yaml_edit(['setup[]', 'git'])

        project['setup'].append('git')

        auth = HTTPBasicAuth(state.dev.envs.BITBUCKET_USER, state.dev.envs.BITBUCKET_PASS_TOKEN)
        
        local("openssl genrsa -out ops/salt/roots/web/files/deploy.pem 2048")
        local("chmod 600 ops/salt/roots/web/files/deploy.pem")
        local("ssh-keygen -f ops/salt/roots/web/files/deploy.pem -y > ops/salt/roots/web/files/deploy.pub")

        ssh_pub_key = local("cat ops/salt/roots/web/files/deploy.pub", capture=True)
        repo_url = "git@bitbucket.org:"+state.dev.envs.BITBUCKET_USER+"/"+state.project.name+".git"

        req = requests.get('https://api.bitbucket.org/2.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.project.name, auth=auth)
        if req.status_code == 404:
            data = {
                'scm': 'git',
                'owner': state.dev.envs.BITBUCKET_USER,
                'repo_slug': state.project.name,
                'is_private': True
            }
            req = requests.post('https://api.bitbucket.org/2.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.project.name, data=data, auth=auth)
            out(req.json())

        req = requests.get('https://bitbucket.org/api/1.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.project.name+'/deploy-keys', auth=auth)
        if req.status_code == 200:
            data = {
                'accountname': state.dev.envs.BITBUCKET_USER,
                'repo_slug': state.project.name,
                'label': state.project.name,
                'key': ssh_pub_key
            }
            req = requests.post('https://bitbucket.org/api/1.0/repositories/'+state.dev.envs.BITBUCKET_USER+'/'+state.project.name+'/deploy-keys', data=data, auth=auth)
            out(req.json())

        with settings(warn_only=True):
            has_git_dir = local("test -d .git", capture=True)
            if has_git_dir.return_code != "0":
                local("git init")

        git_remotes = local("git remote", capture=True)
        if "origin" not in git_remotes:
            local("git remote add origin "+repo_url)
        else:
            local("git remote set-url origin "+repo_url)

        git_remotes = local("git remote", capture=True)
        if "upstream" not in git_remotes:
            local("git remote add upstream git@github.com:stackstrap/craft-ops.git")
        else:
            local("git remote set-url upstream git@github.com:stackstrap/craft-ops.git")

        project['git']['repo'] = repo_url

        yaml_save( { 'project': project } )


    state = get_state()
    if (not method or method == 'web') and ('web' not in state.setup):

        project, private = yaml_edit(['setup[]', 'web'])

        project['setup'].append('web')

        services = state.services
        
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
                key_name=state.web.key_pair+'-'+state.project.name,
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
                name=state.project.name,
                zones=None,
                subnets=subnet_ids,
                listeners=[(80, 80, 'tcp'), (443, 80, 'tcp')],
                security_groups=security_group_ids
            )

            project['web']['load_balancer']['name'] = state.project.name

            conn.register_instances(
                state.project.name,
                [instance.id]
            )

        yaml_save( { 'project': project, 'private': private } )

        # Auto-add the host to known_hosts
        local("ssh-keyscan -t rsa "+state.services.public_ips.web.address+" >> ~/.ssh/known_hosts")

        # Provision the newly created instance
        local("fab --fabfile=ops/fabric/fabfile.py provision:web")
