# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% from "formula/env/macros.sls" import env -%}
{% from "formula/deploy/macros.sls" import deploy %}
{% from "formula/nginx/macros.sls" import nginxsite %}
{% from "formula/php5/macros.sls" import php5_fpm_instance %}
{% from "formula/mysql/macros.sls" import mysql_user_db %}

{% set craft = salt['pillar.get']('craft', {}) %}
{% set database = salt['pillar.get']('database', {}) %}
{% set git = salt['pillar.get']('git', {}) %}
{% set project = salt['pillar.get']('project', {}) %}
{% set web = salt['pillar.get']('web', {}) %}

/var/cache/nginx:
  file.directory:
    - makedirs: True
    - user: www-data
    - group: www-data
    - watch_in:
      - service: nginx

/etc/nginx/nginx.conf:
  file.managed:
    - source: salt://web/files/nginx.conf
    - watch_in:
      - service: nginx

# Setup the web sudo user environment

{% set user = web.user -%}
{% set group = web.group -%}
{% set home = "/home/"+user -%}

{{ env(user, group) }}

# Set up each "stage" user and environment

{% for stage_name, stage in web.stages.items() %}

{% set user = stage.user -%}
{% set group = stage.group -%}

{% set home = '/home/' + user -%}

{% set envs = stage.envs %}

{% set additional_envs = {
  'CRAFT_PATH': home + "/shared/vendor/Craft-Release-" + craft.ref,
  'DB_HOST': database.host,
} %}

{% for key, value in additional_envs.iteritems() %}
    {% do envs.update({key:value}) %}
{% endfor %}

{% set project_path = envs.PROJECT_PATH -%}
{% set vendor_path = envs.VENDOR_PATH -%}

{% set uploads_path = home + "/shared/assets" -%}
{% set plugins_path = home + "/shared/plugins" -%}
{% set craft_path = envs.CRAFT_PATH -%}

{{ env(user, group) }}

{{ home }}/.ssh/deploy.pub:
  file.managed:
    - source: salt://web/files/deploy.pub
    - user: {{ user }}

{{ home }}/.ssh/deploy.pem:
  file.managed:
    - source: salt://web/files/deploy.pem
    - user: {{ user }}
    - mode: 600

{{ deploy(user, group,
          repo=git.repo,
          remote_name='origin',
          bower=True,
          node=True,
          identity=home+'/.ssh/deploy.pem')
}}

{{ php5_fpm_instance(user, group, stage.port,
                     name=project.name,
                     envs=envs)
}}

{{ mysql_user_db(envs.DB_USERNAME, envs.DB_PASSWORD, envs.DB_DATABASE,
                 host=web.private_ip_address,
                 connection={
                   'user': database.username,
                   'pass': database.password,
                   'host': database.host
                 })
}}

{% if web.server_name %}
  {% set web_server_name = web.server_name if (stage_name == "production") else stage_name+'.'+web.server_name -%}
{% else %}
  {% set web_server_name = '_' if (stage_name == "production") else '' -%}
{% endif %}

{% if stage.server_name %}
  {% set server_name = stage.server_name + " " + web_server_name %}
{% else %}
  {% set server_name = web_server_name %}
{% endif %}

{% if stage_name == 'production' %}
  {% set default_server = True %}
{% else %}
  {% set default_server = False %}
{% endif %}

{% if stage.ssl %}
{% set listen = '443' %}
{{ home }}/ssl/{{ stage_name }}.key:
  file.managed:
    - source: salt://web/files/{{ stage.ssl_certificate_key }}
    - user: {{ user }}
    - makedirs: True
{{ home }}/ssl/{{ stage_name }}.crt:
  file.managed:
    - source: salt://web/files/{{ stage.ssl_certificate }}
    - user: {{ user }}
    - makedirs: True
{% else %}
  {% set listen = '80' %}
{% endif %}

{{ nginxsite(user, group,
             project_path=project_path,
             name=project.name,
             server_name=server_name,
             default_server=default_server,
             template="salt://web/files/craft-cms.conf",
             root="public",
             static=project_path+"/public/static",
             listen=listen,
             ssl=stage.ssl,
             defaults={
                'port': stage.port,
                'ssl_certificate': home+'/ssl/'+stage_name+'.crt',
                'ssl_certificate_key': home+'/ssl/'+stage_name+'.key'
             })
}}

{% if stage.ssl %}
{{ nginxsite(user, group,
             name=project.name,
             server_name=server_name,
             template="salt://formula/nginx/files/ssl-redirect.conf")
}}
{% endif %}

{% set deploy_keys = salt['pillar.get']('web:deploy_keys', {}) %}
{% if deploy_keys %}
{{ user }}_authorized_keys:
  file.managed:
    - name: {{ home }}/.ssh/authorized_keys
    - source: salt://web/files/authorized_keys
    - makedirs: True
    - user: {{ user }}
    - template: jinja
    - defaults:
      deploy_keys:
        {% for name, key in deploy_keys.items() %}
        - {{ key }}
        {% endfor %}
{% endif %}

{{ user }}_ssh_config:
  file.managed:
    - name: {{ home }}/.ssh/config
    - source: salt://web/files/ssh_config
    - template: jinja
    - makedirs: True
    - user: {{ user }}

{{ user }}_ssh_known_hosts:
  ssh_known_hosts:
    - name: bitbucket.org
    - present
    - user: {{ user }}

{% set composer_token = salt['pillar.get']('composer:github_token', {}) %}
{% if composer_token %}
{{ user }}_set_composer_github_token:
  cmd.run:
    - name: composer config -g github-oauth.github.com  {{ composer_token }}
    - user: {{ user }}
    - require:
      - cmd: install_composer
      - cmd: move_composer
{% endif %}

{{ user }}_download_craft:
  archive.extracted:
    - name: {{ home }}/shared/vendor
    - source: https://github.com/pixelandtonic/Craft-Release/archive/{{ craft.ref }}.tar.gz
    - source_hash: md5={{ craft.md5 }}
    - archive_format: tar
    - archive_user: {{ user }}
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

{% for plugin_name, plugin in craft.plugins.items() %}
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
    {% if 'base_dir' in plugin %}
    - target: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}/{{ plugin['base_dir'] }}
    {% else %}
    - target: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}
    {% endif %}
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
      stage: {{ stage_name }}
      project_path: {{ project_path }}
      uploads_path: {{ uploads_path }}
      craft_path: {{ craft_path }}
      {% if envs %}
      envs:
        {% for key, value in envs.iteritems() %}
        - key: {{ key }}
          value: "{{ value }}"
        {% endfor %}
      {% else %}
      envs: False
      {% endif %}

{% endfor %}

/etc/sudoers:
  file.managed:
    - source: salt://web/files/sudoers
    - mode: 440

#https://bugs.launchpad.net/ubuntu/+source/php5/+bug/1242376
/etc/init/php5-fpm.conf:
  file.managed:
    - source: salt://web/files/php5-fpm.conf
    - mode: 644
