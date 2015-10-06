# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

base:
  '*':
    - base

  'role:dev':
    - match: pillar
    - dev

  'role:web':
    - match: pillar
    - web
    - web.admin
