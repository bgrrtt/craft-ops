# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% set project = pillar -%}

{% from "stackstrap/env/macros.sls" import env -%}
{% from "stackstrap/deploy/macros.sls" import deploy %}
{% from "stackstrap/nginx/macros.sls" import nginxsite %}
{% from "stackstrap/php5/macros.sls" import php5_fpm_instance %}
{% from "stackstrap/mysql/macros.sls" import mysql_user_db %}

{% set project_name = project['name'] %}

{% set stages = project['web']['stages'] %}

{% for stage in stages %}

{% set user = stages[stage]['user'] -%}
{% set group = stages[stage]['group'] -%}

{% set home = '/home/' + user -%}

{% set project_path = stages[stage]['envs']['PROJECT_PATH'] -%}
{% set vendor_path = stages[stage]['envs']['VENDOR_PATH'] -%}

{% set repo = project['git']['repo'] -%}

{% set port = stages[stage]['port'] -%}

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

{% set uploads_path = home + "/shared/assets" -%}
{% set plugins_path = home + "/shared/plugins" -%}
{% set craft_path = home + "/shared/vendor/Craft-Release-" + project['craft']['ref'] -%}
{% set plugins = project['craft']['plugins'] %}

{% set envs = salt['pillar.get']('web:stages:'+stage+':envs', {}) %}

{% set additional_envs = {
  'CRAFT_PATH': craft_path,
  'DB_HOST': project['services']['database']['host'],
} %}

{% if envs %}
{% for key, value in additional_envs.iteritems() %}
    {% do envs.update({key:value}) %}
{% endfor %}
{% else %}
  {% set envs = additional_envs %}
{% endif %}

{{ php5_fpm_instance(user, group, port,
                     name=project_name,
                     envs=envs)
}}

{% set mysql_user = stages[stage]['envs']['DB_USERNAME'] -%}
{% set mysql_pass = stages[stage]['envs']['DB_PASSWORD'] -%}
{% set mysql_db = stages[stage]['envs']['DB_DATABASE'] -%}

{{ mysql_user_db(mysql_user, mysql_pass, mysql_db,
                 host=project['web']['private_ip_address'],
                 connection={
                   'user': project['services']['database']['username'],
                   'pass': project['services']['database']['password'],
                   'host': project['services']['database']['host']
                 })
}}

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

{% if stages[stage]['ssl'] %}
{% set listen = '443' %}
{{ home }}/ssl/{{ stage }}.key:
  file.managed:
    - source: salt://web/files/{{ stages[stage]['ssl_certificate_key'] }}
    - user: {{ user }}
    - makedirs: True
{{ home }}/ssl/{{ stage }}.crt:
  file.managed:
    - source: salt://web/files/{{ stages[stage]['ssl_certificate'] }}
    - user: {{ user }}
    - makedirs: True
{% else %}
  {% set listen = '80' %}
{% endif %}

{{ nginxsite(user, group,
             project_path=project_path,
             name=project_name,
             server_name=server_name,
             default_server=default_server,
             template="salt://web/files/craft-cms.conf",
             root="public",
             static=project_path+"/public/static",
             listen=listen,
             ssl=stages[stage]['ssl'],
             defaults={
                'port': port,
                'ssl_certificate': home+'/ssl/'+stage+'.crt',
                'ssl_certificate_key': home+'/ssl/'+stage+'.key'
             })
}}

{% if stages[stage]['ssl'] %}
{{ nginxsite(user, group,
             name=project_name,
             server_name=server_name,
             template="salt://stackstrap/nginx/files/ssl-redirect.conf")
}}
{% endif %}

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

{% if project['composer']['github_token'] %}
{{ user }}_set_composer_github_token:
  cmd.run:
    - name: composer config -g github-oauth.github.com  {{ project['composer']['github_token'] }}
    - user: {{ user }}
    - require:
      - cmd: install_composer
      - cmd: move_composer
{% endif %}

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

{% set plugins = salt['pillar.get']('craft:plugins', {}) %}
{% for plugin_name, plugin in plugins.items() %}
{{ user }}_download_craft_{{ plugin_name }}_plugin:
  archive.extracted:
    - name: {{ vendor_path }}
    - source: https://github.com/{{ plugin['author'] }}/{{ plugin['repo_name'] }}/archive/{{ plugin['ref'] }}.tar.gz 
    - source_hash: md5={{ plugin['md5'] }}
    - archive_format: tar
    - user: {{ user }}
    - group: {{ group }}
    - if_missing: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}

{{ home }}/shared/plugins/{{ plugin_name }}:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    - target: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}/{{ plugin['name'] }}
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
