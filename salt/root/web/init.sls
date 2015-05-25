# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

php5-mcrypt:
  pkg.installed

php-mcrypt-enable:
  cmd.run:
    - name: php5enmod mcrypt
    - require:
      - pkg: php5-mcrypt

php5-restart:
  cmd.run:
    - name: service php5-fpm restart
    - require:
      - cmd: php-mcrypt-enable

install_composer:
  cmd:
    - run
    - name: curl -sS https://getcomposer.org/installer | php -- --install-dir=/opt
    - unless: test -e /opt/composer.phar
    - require:
      - pkg: php5-fpm

/usr/local/bin/composer:
  file.symlink:
    - target: /opt/composer.phar

{% from "stackstrap/env/macros.sls" import env -%}
{% from "stackstrap/deploy/macros.sls" import deploy %}
{% from "stackstrap/nginx/macros.sls" import nginxsite %}
{% from "stackstrap/php5/macros.sls" import php5_fpm_instance %}
{% from "stackstrap/mysql/macros.sls" import mysql_user_db %}
{% from "stackstrap/nvmnode/macros.sls" import nvmnode %}

{% set project = pillar -%}
{% set project_name = project['name'] %}

{% set stages = project['web']['stages'] %}

{% set aws_access_key = project['aws']['access_key'] -%}
{% set aws_secret_key = project['aws']['secret_key'] -%}

{% for stage in stages %}

{% set user = stages[stage]['user'] -%}
{% set group = stages[stage]['group'] -%}

{% set home = '/home/' + user -%}

{% set project_path = home + '/current' -%}
{% set repo = project['git']['repo'] -%}

{% set port = stages[stage]['port'] -%}

{% set mysql_user = stages[stage]['mysql_user'] -%}
{% set mysql_pass = stages[stage]['mysql_pass'] -%}
{% set mysql_db = stages[stage]['mysql_db'] -%}

{% set uploads_path = home + "/shared/assets" -%}
{% set craft_path = home + "/shared/vendor/Craft-Release-master" -%}

{{ env(user, group) }}

{{ user }}_private_key:
  file.managed:
    - name: {{ home }}/.ssh/web.pem
    - source: salt://web/files/web.pem
    - makedirs: True
    - user: {{ user }}
    - mode: 600

{{ deploy(user, group,
          repo=repo,
          remote_name='bitbucket',
          identity=home+'/.ssh/web.pem')
}}

{{ nvmnode(user, group,
           ignore_package_json=True,
           node_globals=['bower', 'grunt', 'node-sass', 'harp']) 
}}

{{ user }}_install_harp:
  cmd.run:
    - name: /bin/bash -c "source ~/.nvm/nvm.sh; npm install -g harp"
    - user: {{ user }}
    - unless: /bin/bash -c "source ~/.nvm/nvm.sh; npm -g ls harp | grep harp"
    - check_cmd:
      - /bin/true
    - require:
      - cmd: {{ user }}_install_node

{{ php5_fpm_instance(user, group, port,
                     name=project_name,
                     envs={
                      'PROJECT_PATH': project_path,
                      'UPLOADS_PATH': uploads_path,
                      'CRAFT_ENVIRONMENT': stage,
                      'CRAFT_PATH': craft_path,
			                'MYSQL_USER': mysql_user,
			                'MYSQL_PASS': mysql_pass,
			                'MYSQL_DB': mysql_db,
                     })
}}

{{ mysql_user_db(mysql_user, mysql_pass, mysql_db) }}

{% if project['web']['server_name'] is not none  %}
  {% set web_server_name = project['web']['server_name'] if (stage == "production") else stage+'.'+project['web']['server_name'] -%}

  {% if stages[stage]['server_name'] is not none %}
    {% set server_name = stages[stage]['server_name'] + " " + web_server_name %}
  {% else %}
    {% set server_name = web_server_name %}
  {% endif %}

{% else %}
  {% set server_name = project_name -%}
{% endif %}

{{ nginxsite(user, group,
             project_path=project_path,
             name=project_name,
             server_name=server_name,
             template="salt://web/files/craft-cms.conf",
             root="current/public",
             cors="*",
             defaults={
                'port': port
             })
}}

{{ user }}_authorized_keys:
  file.managed:
    - name: {{ home }}/.ssh/authorized_keys
    - source: salt://web/files/authorized_keys
    - makedirs: True
    - user: {{ user }}

{{ user }}_ssh_config:
  file.managed:
    - name: {{ home }}/.ssh/config
    - source: salt://web/files/ssh_config
    - template: jinja
    - makedirs: True
    - user: {{ user }}

{{ user }}_public_key:
  file.managed:
    - name: {{ home }}/.ssh/web.pub
    - source: salt://web/files/web.pub
    - makedirs: True
    - user: {{ user }}

{{ user }}_ssh_known_hosts:
  ssh_known_hosts:
    - name: bitbucket.org
    - present
    - user: {{ user }}

{{ user }}_download_craft:
  archive.extracted:
    - name: {{ home }}/shared/vendor
    - source: https://github.com/pixelandtonic/Craft-Release/archive/master.tar.gz 
    - source_hash: md5=0cf267bac9a021a4adcbf983dfd0f8ef
    - archive_format: tar
    - archive_user: {{ home }}
    - if_missing: {{ home }}/shared/vendor/Craft-Release-master

{{ home }}/shared/vendor/Craft-Release-master:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True
    - recurse:
      - user
      - group

{{ user }}_bowerrc:
  file.managed:
    - user: {{ user }}
    - group: {{ group }}
    - source: salt://web/files/.bowerrc
    - name: {{ home }}/.bowerrc
    - require:
      - user: {{ user }}

{{ user }}_profile_setup:
  file.managed:
    - source: salt://web/files/ssh_profile
    - name: {{ home }}/.profile
    - user: {{ user }}
    - template: jinja
    - require:
      - user: {{ user }}
    - defaults:
      stage: {{ stage }}
      project_path: {{ project_path }}
      mysql_user: {{ mysql_user }}
      mysql_pass: {{ mysql_pass }}
      mysql_db: {{ mysql_db }}
      {% if aws_access_key %}
      aws_access_key: {{ aws_access_key }}
      aws_secret_key: {{ aws_secret_key }}
      {% endif %}
      uploads_path: {{ uploads_path }}
      craft_path: {{ craft_path }}

{% endfor %}
