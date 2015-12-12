# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% from "formula/env/macros.sls" import env -%}

{% set project = salt['pillar.get']('project', {}) %}
{% set web = salt['pillar.get']('web', {}) %}

{% set user = web.admin.user -%}
{% set group = web.admin.group -%}

{% set home = "/home/"+user -%}

{{ env(user, group) }}

python_requirements:
  pip.installed:
    - requirements: salt://web/files/requirements.txt

admin_private_key:
  file.managed:
    - name: {{ home }}/.ssh/web.pem
    - source: salt://web/files/deploy.pem
    - makedirs: True
    - user: {{ user }}
    - mode: 600

admin_profile_setup:
  file.managed:
    - source: salt://web/files/ssh_profile_admin
    - name: {{ home }}/.profile
    - user: {{ user }}
    - template: jinja
