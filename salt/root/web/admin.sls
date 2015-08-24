# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% from "stackstrap/env/macros.sls" import env -%}

{% set project = pillar -%}
{% set project_name = project['name'] -%}

{% set user = 'ubuntu' -%}
{% set group = 'ubuntu' -%}

{% set home = "/home/"+user -%}
{% set project_path = "/project" -%}

{{ env(user, group) }}

python_requirements:
  cmd:
    - run
    - name: "pip install -r {{ project_path }}/salt/root/web/files/requirements.txt"

admin_private_key:
  file.managed:
    - name: {{ home }}/.ssh/web.pem
    - source: salt://web/files/web.pem
    - makedirs: True
    - user: {{ user }}
    - mode: 600

admin_profile_setup:
  file.managed:
    - source: salt://web/files/ssh_profile_admin
    - name: {{ home }}/.profile
    - user: {{ user }}
    - template: jinja
    - defaults:
      project_path: {{ project_path }}
