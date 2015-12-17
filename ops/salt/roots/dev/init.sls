# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% from "formula/supervisor/macros.sls" import supervise -%}
{% from "formula/nginx/macros.sls" import nginxsite %}
{% from "formula/php5/macros.sls" import php5_fpm_instance %}
{% from "formula/mysql/macros.sls" import mysql_user_db %}
{% from "formula/env/macros.sls" import env %}

{% set project = salt['pillar.get']('project', {}) %}
{% set services = salt['pillar.get']('services', {}) %}
{% set dev = salt['pillar.get']('dev', {}) %}
{% set git = salt['pillar.get']('git', {}) %}
{% set craft = salt['pillar.get']('craft', {}) %}

{% set user = dev.user %}
{% set group = dev.group %}

{% set envs = dev.envs %}

{% set additional_envs = {
  'CRAFT_PATH': envs.VENDOR_PATH + "/Craft-Release-" + craft.ref
} %}

{% for key, value in additional_envs.iteritems() %}
    {% do envs.update({key:value}) %}
{% endfor %}

{% set home = envs.HOME %}
{% set project_path = envs.PROJECT_PATH %}
{% set assets_path = project_path + '/assets' %}
{% set craft_path = envs.CRAFT_PATH %}
{% set vendor_path = envs.VENDOR_PATH %}
{% set uploads_path = envs.UPLOADS_PATH %}

{{ env(user, group) }}
  
{{ php5_fpm_instance(user, group, '5000',
                     envs=envs)
}}

{{ mysql_user_db(envs.DB_USERNAME, envs.DB_PASSWORD,
                 dump=project_path+'/ops/database.sql') }}

{{ nginxsite(user, group,
             template="salt://dev/files/craft-cms.conf",
	           root="public",
             listen="8000",
             server_name="_",
             defaults={
                'port': '5000'
             })
}}

{{ user }}_ssh_config:
  file.managed:
    - name: {{ home }}/.ssh/config
    - source: salt://dev/files/ssh_config
    - template: jinja
    - makedirs: True
    - user: {{ user }}

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

{{ project_path }}/public/plugins.php:
  file.managed:
    - source: salt://dev/files/plugins.php
    - user: {{ user }}
    - group: {{ group }}

{{ vendor_path }}:
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
    - name: {{ vendor_path }}
    - source: https://github.com/pixelandtonic/Craft-Release/archive/{{ craft.ref }}.tar.gz
    - source_hash: md5={{ craft.md5 }}
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


{% for name, plugin in craft.plugins.items() %}
download_craft_{{ name }}_plugin:
  archive.extracted:
    - name: {{ vendor_path }}
    - source: https://github.com/{{ plugin['author'] }}/{{ plugin['repo_name'] }}/archive/{{ plugin['ref'] }}.tar.gz
    - source_hash: md5={{ plugin['md5'] }}
    - archive_format: tar
    - user: {{ user }}
    - group: {{ group }}
    - if_missing: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}

{{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}:
  file.directory:
    - user: {{ user }}
    - group: {{ group }}
    - makedirs: True
    - recurse:
      - user
      - group

{{ home }}/plugins/{{ name }}:
  file.symlink:
    - user: {{ user }}
    - group: {{ group }}
    {% if 'base_dir' in plugin %}
    - target: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}/{{ plugin['base_dir'] }}
    {% else %}
    - target: {{ vendor_path }}/{{ plugin['repo_name'] }}-{{ plugin['ref'] }}
    {% endif %}
{% endfor %}

{% if envs.AWS_ACCESS_KEY %}
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
        aws_access_key: {{ envs.AWS_ACCESS_KEY }}
        aws_secret_key: {{ envs.AWS_SECRET_KEY }}
        region: us-east-1

{{ home }}/.boto:
  file.managed:
    - source: salt://dev/files/.boto
    - template: jinja
    - user: {{ user }}
    - group: {{ group }}
    - mode: 600
    - defaults:
        aws_access_key: {{ envs.AWS_ACCESS_KEY }}
        aws_secret_key: {{ envs.AWS_SECRET_KEY }}
        region: {{ services.region }}
{% endif %}

dev_node_globals:
  npm.installed:
    - pkgs:
      - wetty
      - browser-sync
    - require:
      - file: /usr/local/bin/node
      - file: /usr/local/bin/npm

{{ home }}/bs-config.js:
  file.managed:
    - source: salt://dev/files/bs-config.js
    - user: {{ user }}

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
    - onlyif: test -f {{ project_path }}/bower.json
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
        git_email: {{ git.email }}
        git_name: {{ git.name }}

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
      envs:
        {% for key, value in envs.iteritems() %}
        - key: {{ key }}
          value: "{{ value }}"
        {% endfor %}

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
        },
        "browser-sync": {
          "command": "/usr/local/bin/browser-sync start --config /home/vagrant/bs-config.js",
            "directory": project_path,
            "user": user
        }
    })
}}

/usr/local/transcrypt:
  archive.extracted:
    - source: https://github.com/elasticdog/transcrypt/archive/v0.9.7.tar.gz
    - source_hash: md5=b37aa6539b344ea51c9a52080ad6b59c
    - archive_format: tar
    - tar_options: --strip-components=1
    - user: {{ user }}
    - group: {{ group }}

/usr/local/bin/transcrypt:
  file.symlink:
    - target: /usr/local/transcrypt/transcrypt

#https://bugs.launchpad.net/ubuntu/+source/php5/+bug/1242376
/etc/init/php5-fpm.conf:
  file.managed:
    - source: salt://dev/files/php5-fpm.conf
    - mode: 644
