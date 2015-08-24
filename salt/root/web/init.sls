# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

node_global_browserify:
  cmd:
    - run
    - name: npm install -g browserify
    - unless: npm -g ls browserify | grep browserify
    - require:
      - pkg: nodejs

{% from "stackstrap/env/macros.sls" import env -%}
{% from "stackstrap/deploy/macros.sls" import deploy %}
{% from "stackstrap/nginx/macros.sls" import nginxsite %}
{% from "stackstrap/php5/macros.sls" import php5_fpm_instance %}
{% from "stackstrap/mysql/macros.sls" import mysql_user_db %}

{% set project = pillar -%}
{% set project_name = project['name'] %}

{% set stages = project['web']['stages'] %}

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
{% set php_vendor_path = home + "/shared/vendor" -%}
{% set plugins_path = home + "/shared/plugins" -%}
{% set craft_path = home + "/shared/vendor/Craft-Release-" + project['craft']['ref'] -%}
{% set plugins = project['craft']['plugins'] %}

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
          remote_name='origin',
          bower=True,
          node=True,
          identity=home+'/.ssh/web.pem')
}}

{% set php_envs = {
  'PROJECT_PATH': project_path,
  'UPLOADS_PATH': uploads_path,
  'CRAFT_ENVIRONMENT': stage,
  'CRAFT_PATH': craft_path,
  'MYSQL_USER': mysql_user,
  'MYSQL_PASS': mysql_pass,
  'MYSQL_DB': mysql_db,
} %}

{% if stages[stage]['envs'] %}
{% for key, value in salt['pillar.get']('web:stages:'+stage+':envs', {}).iteritems() %}
    {% do php_envs.update({key:value}) %}
{% endfor %}
{% endif %}

{{ php5_fpm_instance(user, group, port,
                     name=project_name,
                     envs=php_envs)
}}

{{ mysql_user_db(mysql_user, mysql_pass, mysql_db) }}

{% if project['web']['server_name'] %}
  {% set web_server_name = project['web']['server_name'] if (stage == "production") else stage+'.'+project['web']['server_name'] -%}
{% else %}
  {% set web_server_name = '_' if (stage == "production") else '' -%}
{% endif %}

{% if stages[stage]['server_name'] %}
  {% set server_name = stages[stage]['server_name'] + " " + web_server_name %}
{% else %}
  {% set server_name = web_server_name %}
{% endif %}

{% if stage == 'production' %}
  {% set default_server = True %}
{% else %}
  {% set default_server = False %}
{% endif %}

{{ nginxsite(user, group,
             project_path=project_path,
             name=project_name,
             server_name=server_name,
             default_server=default_server,
             template="salt://web/files/craft-cms.conf",
             root="public",
             static=project_path+"/public/static",
             cors="*",
             defaults={
                'port': port
             })
}}

{% if project['web']['deploy_keys'] %}
{{ user }}_authorized_keys:
  file.managed:
    - name: {{ home }}/.ssh/authorized_keys
    - source: salt://web/files/authorized_keys
    - makedirs: True
    - user: {{ user }}
    - template: jinja
    - defaults:
      deploy_keys:
        {% for name in project['web']['deploy_keys'] %}
        - {{ project['web']['deploy_keys'][name] }}
        {% endfor %}
{% endif %}

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
    - source: https://github.com/pixelandtonic/Craft-Release/archive/{{ project['craft']['ref'] }}.tar.gz
    - source_hash: md5={{ project['craft']['md5'] }}
    - archive_format: tar
    - archive_user: {{ home }}
    - if_missing: {{ craft_path }}

{{ craft_path }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True
    - recurse:
      - user
      - group

{{ plugins_path }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True

{% for plugin in plugins %}
{{ user }}_download_craft_{{ plugin['name'] }}_plugin:
  archive.extracted:
    - name: {{ php_vendor_path }}
    - source: https://github.com/{{ plugin['author'] }}/{{ plugin['repo_name'] }}/archive/{{ plugin['ref'] }}.tar.gz 
    - source_hash: md5={{ plugin['md5'] }}
    - archive_format: tar
    - user: {{ user }}
    - group: {{ group }}
    - if_missing: {{ php_vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}

{{ home }}/shared/plugins/{{ plugin['name'] }}:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ php_vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}/{{ plugin['name'] }}
{% endfor %}

{{ user }}_bowerrc:
  file.managed:
    - user: {{ user }}
    - group: {{ group }}
    - source: salt://web/files/.bowerrc
    - template: jinja
    - name: {{ home }}/.bowerrc
    - require:
      - user: {{ user }}
    - defaults:
      home: {{ home }}

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
      uploads_path: {{ uploads_path }}
      craft_path: {{ craft_path }}
      {% if stages[stage]['envs'] %}
      envs:
        {% for key, value in salt['pillar.get']('web:stages:'+stage+':envs', {}).iteritems() %}
        - key: {{ key }}
          value: "{{ value }}"
        {% endfor %}
      {% else %}
      envs: False
      {% endif %}

{% endfor %}

#https://bugs.launchpad.net/ubuntu/+source/php5/+bug/1242376
/etc/init/php5-fpm.conf:
  file.managed:
    - source: salt://web/files/php5-fpm.conf
    - mode: 644
