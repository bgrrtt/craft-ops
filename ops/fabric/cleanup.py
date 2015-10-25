import boto.vpc
import boto.ec2
import boto.ec2.elb
import boto.rds2
import json
import pprintpp
import requests
import time
import urllib

from fabric.api import *
from requests.auth import HTTPBasicAuth
from utils import *


@task(default=True)
@hosts()
def cleanup(method=False):

    state = get_state()
    if (not method or method == 'database') and ('database' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('database')

        conn = boto.rds2.connect_to_region(state.services.region)

        conn.delete_db_instance(state.project.name, skip_final_snapshot=True)

        database = conn.describe_db_instances(db_instance_identifier=state.project.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]

        while database['DBInstanceStatus'] == 'deleting':
            print '...database instance status: %s' % database['DBInstanceStatus']
            time.sleep(10)
            #RDS2 does not offer an "update" method
            try:
                database = conn.describe_db_instances(db_instance_identifier=state.project.name)['DescribeDBInstancesResponse']['DescribeDBInstancesResult']['DBInstances'][0]
            except:
                break

        conn.delete_db_subnet_group(state.database.subnet_group)

        project['database'].pop('host')
        project['database'].pop('subnet_group')

        # Clear password and host for each stage
        for name, item in state.web.stages.items():
            private['web']['stages'][name]['envs'].pop('DB_PASSWORD', None)

        yaml_save( { 'project': project, 'private': private } )

    state = get_state()
    if (not method or method == 'web') and ('web' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('web')

        services = state.services

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

    state = get_state()
    if (not method or method == 'services') and ('services' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('services')

        services = state.services

        conn = boto.vpc.connect_to_region(services.region)

        for name, item in services.key_pairs.items():
            conn.delete_key_pair(name+'-'+state.project.name)
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

    state = get_state()
    if (not method or method == "git") and ('git' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('git')

        services = state.services

        project_name = state.project.name
        bitbucket_user = state.dev.envs.BITBUCKET_USER
        bitbucket_token = state.dev.envs.BITBUCKET_PASS_TOKEN
        auth = HTTPBasicAuth(bitbucket_user, bitbucket_token)

        req = requests.get('https://api.bitbucket.org/2.0/repositories/'+bitbucket_user+'/'+project_name, auth=auth)

        if req.status_code == 200:
            data = { 'owner': bitbucket_user, 'repo_slug': project_name }
            req = requests.delete('https://api.bitbucket.org/1.0/repositories/'+bitbucket_user+'/'+project_name, data=data, auth=auth)

            if req.status_code == 204:
                project.pop('git')

        local("rm -f ops/salt/roots/web/files/deploy.pem")
        local("rm -f ops/salt/roots/web/files/deploy.pub")

        yaml_save( { 'project': project } )

    state = get_state()
    if (not method or method == 'craft') and ('craft' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('craft')

        local('mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD -Nse \'show tables\' $DB_DATABASE | while read table; do mysql -u $DB_USERNAME -h $DB_HOST -p$DB_PASSWORD -e "SET FOREIGN_KEY_CHECKS = 0; drop table $table" $DB_DATABASE; done')

        yaml_save( { 'project': project, 'private': private } )

    state = get_state()
    if (not method or method == 'dev') and ('dev' in state.setup):

        project, private = yaml_edit()

        project['setup'].remove('dev')

        local('rm -f ops/keys/dev.pem')
        local('rm -f ops/keys/dev.pub')

        project['web']['deploy_keys'].pop('dev')

        yaml_save( { 'project': project, 'private': private } )
            
