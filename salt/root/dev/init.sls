# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% from "stackstrap/supervisor/macros.sls" import supervise -%}
{% from "stackstrap/nginx/macros.sls" import nginxsite %}
{% from "stackstrap/php5/macros.sls" import php5_fpm_instance %}
{% from "stackstrap/mysql/macros.sls" import mysql_user_db %}
{% from "stackstrap/env/macros.sls" import env %}

{% set project = pillar -%}

{% set project_name = project['name'] -%}
{% set aws_access_key = project['aws']['access_key'] -%}
{% set aws_secret_key = project['aws']['secret_key'] -%}
{% set bitbucket_user = project['bitbucket']['user'] -%}
{% set bitbucket_pass_token = project['bitbucket']['token'] -%}

{% set user = project['dev']['user'] -%}
{% set group = project['dev']['group'] -%}
{% set home = "/home/" + user -%}
{% set project_path = project['dev']['path'] -%}
{% set assets_path = project['dev']['path'] + "/assets" -%}

{% set git_repo = project['git']['repo'] %}
{% set git_email = project['git']['email'] %}
{% set git_name = project['git']['name'] %}

{% set mysql_user = project['dev']['envs']['DB_USERNAME'] -%}
{% set mysql_pass = project['dev']['envs']['DB_PASSWORD'] -%}
{% set mysql_db = project['dev']['envs']['DB_DATABASE'] -%}
{% set mysql_host = project['dev']['envs']['DB_HOST'] -%}

{{ mysql_user_db(mysql_user, mysql_pass) }}

{% set uploads_path = project_path + "/public/assets" -%}
{% set php_vendor_path = project_path + "/vendor" -%}
{% set vagrant_host_os = salt['grains.get']('vagrant_host_os', '') %}
{% if vagrant_host_os == 'windows' %}
  {% set php_vendor_path = home + "/vendor" -%}
{% endif %}
{% set craft_path = php_vendor_path + "/Craft-Release-" + project['craft']['ref'] -%}
{% set plugins = project['craft']['plugins'] %}

python_requirements:
  pip.installed:
    - requirements: salt://dev/files/requirements.txt

configure_legit_remote:
  cmd.run:
    - name: git config legit.remote origin
    - user: {{ user }}
    - cwd: {{ project_path }}
    - require:
      - pip: python_requirements

install_legit_aliases:
  cmd.run:
    - name: legit install
    - cwd: {{ project_path }}
    - user: {{ user }}
    - require:
      - pip: python_requirements

{{ user }}_mysql_import:
  cmd.run:
    - name: unzip -p {{ project_path }}/salt/root/dev/files/craft-cms-backup.zip | mysql -u {{ mysql_user }} -p{{ mysql_pass }} {{ mysql_db }}
    - unless: mysql -u {{ mysql_user }} -p{{ mysql_pass }} {{ mysql_db }} -e "SHOW TABLES LIKE 'craft_info'" | grep 'craft_info'

{{ env(user, group) }}

{{ user }}_ssh_config:
  file.managed:
    - name: {{ home }}/.ssh/config
    - source: salt://dev/files/ssh_config
    - template: jinja
    - makedirs: True
    - user: {{ user }}

{% set php_envs = {
  'CRAFT_ENVIRONMENT': 'local',
  'CRAFT_PATH': craft_path,
  'PROJECT_PATH': project_path,
  'UPLOADS_PATH': uploads_path,
  'MYSQL_USER': mysql_user,
  'MYSQL_PASS': mysql_pass,
  'MYSQL_DB': mysql_db
} %}

{% if project['dev']['envs'] %}
{% for key, value in salt['pillar.get']('dev:envs', {}).iteritems() %}
    {% do php_envs.update({key:value}) %}
  {% endfor %}
{% endif %}
  
{{ php5_fpm_instance(user, group, '5000',
                     envs=php_envs)
}}

{{ nginxsite(user, group,
             template="salt://dev/files/craft-cms.conf",
	           root="public",
             listen="8000",
             server_name="_",
             cors="*",
             defaults={
                'port': '5000'
             })
}}

{{ project_path }}/public/plugins.php:
  file.managed:
    - source: salt://dev/files/plugins.php
    - user: {{ user }}
    - group: {{ group }}

{{ php_vendor_path }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}

{{ uploads_path }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}

{{ home }}/plugins:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}

{{ home }}/storage:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}

download_craft:
  archive.extracted:
    - name: {{ php_vendor_path }}
    - source: https://github.com/pixelandtonic/Craft-Release/archive/{{ project['craft']['ref'] }}.tar.gz
    - source_hash: md5={{ project['craft']['md5'] }}
    - archive_format: tar
    - user: {{ user }}
    - group: {{ group }}
    - if_missing: {{ craft_path }}

{{ craft_path }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True
    - recurse:
      - user
      - group

/usr/local/bin/yiic:
  file.symlink:
    - target: {{ craft_path }}/app/etc/console/yiic

{{ craft_path }}/config:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ project_path }}/craft/config

{{ craft_path }}/plugins:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ home }}/plugins

{{ craft_path }}/storage:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ home }}/storage

{{ craft_path }}/templates:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ project_path }}/templates

{% for plugin in plugins %}
download_craft_{{ plugin['name'] }}_plugin:
  archive.extracted:
    - name: {{ php_vendor_path }}
    - source: https://github.com/{{ plugin['author'] }}/{{ plugin['repo_name'] }}/archive/{{ plugin['ref'] }}.tar.gz
    - source_hash: md5={{ plugin['md5'] }}
    - archive_format: tar
    - user: {{ user }}
    - group: {{ group }}
    - if_missing: {{ php_vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}

{{ php_vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True
    - recurse:
      - user
      - group

{{ home }}/plugins/{{ plugin['name'] }}:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ php_vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}/{{ plugin['name'] }}
{% endfor %}

{% if aws_access_key %}
{{ home }}/.aws:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - mode: 755

{{ home }}/.aws/config:
  file.managed:
    - source: salt://dev/files/aws.config
    - template: jinja
    - user: {{ user }}
    - group: {{ group }}
    - mode: 600
    - defaults:
        aws_access_key: {{ aws_access_key }}
        aws_secret_key: {{ aws_secret_key }}
        region: us-east-1

{{ home }}/.boto:
  file.managed:
    - source: salt://dev/files/.boto
    - template: jinja
    - user: {{ user }}
    - group: {{ group }}
    - mode: 600
    - defaults:
        aws_access_key: {{ aws_access_key }} 
        aws_secret_key: {{ aws_secret_key }} 
        region: {{ project['services']['region'] }}
{% endif %}

node_global_wetty:
  cmd:
    - run
    - name: npm install -g wetty
    - unless: npm -g ls wetty | grep wetty
    - require:
      - pkg: nodejs

node_global_weinre:
  cmd:
    - run
    - name: npm install -g weinre@2.0.0-pre-I0Z7U9OV
    - unless: npm -g ls weinre | grep weinre
    - require:
      - pkg: nodejs

/etc/rc.local:
  file.managed:
    - source: salt://dev/files/rc.local
    - template: jinja
    - defaults:
        home: {{ home }}
        name: dev

{{ user }}_bowerrc:
  file.managed:
    - user: {{ user }}
    - group: {{ group }}
    - source: salt://dev/files/.bowerrc
    - name: {{ home }}/.bowerrc
    - require:
      - user: {{ user }}

install_bower_components:
  cmd.run:
    - name: bower install
    - cwd: {{ project_path }}
    - user: {{ user }}
    - require:
      - file: {{ user }}_bowerrc

{{ user }}_git_config:
  file.managed:
    - user: {{ user }}
    - group: {{ group }}
    - source: salt://dev/files/git_config
    - name: {{ home }}/.gitconfig
    - template: jinja
    - require:
      - user: {{ user }}
    - defaults:
        home: {{ home }}
        git_email: {{ git_email }}
        git_name: {{ git_name }}

{{ user }}_ssh_profile:
  file.managed:
    - user: {{ user }}
    - group: {{ group }}
    - source: salt://dev/files/ssh_profile
    - name: {{ home }}/.profile
    - template: jinja
    - require:
      - user: {{ user }}
    - defaults:
      project_path: {{ project_path }}
      mysql_user: {{ mysql_user }}
      mysql_pass: {{ mysql_pass }}
      mysql_db: {{ mysql_db }}
      {% if aws_access_key %}
      aws_access_key: {{ aws_access_key }}
      aws_secret_key: {{ aws_secret_key }}
      {% endif %}
      {% if bitbucket_user %}
      bitbucket_user: {{ bitbucket_user }}
      bitbucket_pass_token: {{ bitbucket_pass_token }}
      {% endif %}
      uploads_path: {{ uploads_path }}
      craft_path: {{ craft_path }}
      {% if project['dev']['envs'] %}
      envs:
        {% for key, value in salt['pillar.get']('dev:envs', {}).iteritems() %}
        - key: {{ key }}
          value: "{{ value }}"
        {% endfor %}
      {% else %}
      envs: False
      {% endif %}

{{ supervise("dev", home, user, group, {
        "harp": {
            "command": "harp server",
            "directory": assets_path,
            "user": user
        },
        "wetty": {
          "command": "wetty -p 3000 --sshuser=vagrant",
            "directory": project_path,
            "user": user
        }
    })
}}

#https://bugs.launchpad.net/ubuntu/+source/php5/+bug/1242376
/etc/init/php5-fpm.conf:
  file.managed:
    - source: salt://dev/files/php5-fpm.conf
    - mode: 644
