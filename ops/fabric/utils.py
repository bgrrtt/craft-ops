from bunch import bunchify
from pprintpp import pprint as out
from fabric.api import env

import copy
import os
import random
import ruamel.yaml
import string
import yaml


def set_stage(stage_name):
    state = get_state()

    stage = state.web.stages[stage_name]

    out('Using stage: '+stage_name)

    return stage

def set_env(role, stage=False):
    state = get_state()

    server = state.services.public_ips.web.address

    if role == 'dev':
        env.user = state.dev.user
        env.hosts = ["localhost"]
        env.host = ["localhost"]
        env.host_string = "localhost"
    else:
        env.user = stage.user
        env.hosts = [server]
        env.host = [server]
        env.host_string = str(server)

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
    with open('ops/config/defaults.conf') as defaults_file:
        defaults_file_content = defaults_file.read()

    state = yaml.load(defaults_file_content)

    if os.path.isfile(os.environ['HOME']+'/ops.conf'):
        with open(os.environ['HOME']+'/ops.conf') as ops_file:
            ops_file_content = ops_file.read()
        ops = yaml.load(ops_file_content)
        state = dict_merge(state, ops)

    if os.path.isfile('ops/config/project.conf'):
        with open('ops/config/project.conf') as project_file:
            project_file_content = project_file.read()
        project = yaml.load(project_file_content)
        state = dict_merge(state, project)

    if os.path.isfile('ops/config/private.conf'):
        with open('ops/config/private.conf') as private_file:
            private_file_content = private_file.read()
        private = yaml.load(private_file_content)
        state = dict_merge(state, private)

    if bunch:
        return bunchify(state)
    else:
        return state

def yaml_edit(tree=False):
    files = { "project": {}, "private": {} }

    for name, item in files.items():
        if os.path.isfile('ops/config/'+name+'.conf'): 
            with open('ops/config/'+name+'.conf') as opened_file:
                file_content = opened_file.read()
            config = ruamel.yaml.load(file_content, ruamel.yaml.RoundTripLoader)
        else:
            config = ruamel.yaml.load('dummy: null', ruamel.yaml.RoundTripLoader)
            config.pop('dummy')

        if tree:
            for path in tree: 
                path = path.split('.')
                for index, value in enumerate(path):

                    if '[]' in value:
                        value = value.replace('[]','')   
                        default = []
                    else:
                        default = {}

                    if index == 0:
                        if value not in config or not config[value]:
                            config[value] = default

                    if index == 1:
                        if value not in config[path[0]]:
                            config[path[0]][value] = default

                    if index == 2:
                        if value not in config[path[0]][path[1]]:
                            config[path[0]][path[1]][value] = default

                    if index == 3:
                        if value not in config[path[0]][path[1]][path[2]]:
                            config[path[0]][path[1]][path[2]][value] = default

        if name == 'project': 
            files['project'] = config

        if name == 'private': 
            files['private'] = config

    return files['project'], files['private']


def yaml_save(objects):
    for name, item in objects.items():
        item = remove_empty(item)
        
        if item:
            with open('ops/config/'+name+'.conf', 'w+') as outfile:
                outfile.write( ruamel.yaml.dump(item, Dumper=ruamel.yaml.RoundTripDumper) )
        else:
            try:
                os.remove('ops/config/'+name+'.conf')
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
