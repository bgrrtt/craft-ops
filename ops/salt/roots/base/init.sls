# -*- mode: yaml -*-
# vim: set ft=yaml ts=2 sw=2 et sts=2 :

{% set project = pillar -%}

include:
  - formula.env
  - formula.supervisor
  - formula.nginx
  - formula.node
  - formula.php5.fpm
  - formula.mysql.server
  - formula.mysql.client

node_globals:
  npm.installed:
    - pkgs:
      - harp
      - bower
    - require:
      - file: /usr/local/bin/node
      - file: /usr/local/bin/npm

remove-nginx-default-conf:
  file:
    - absent
    - names:
      - /etc/nginx/sites-enabled/default
      - /etc/nginx/sites-available/default
    - require:
      - pkg: nginx
    - watch_in:
      - service: nginx

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
  cmd.run:
    - name: curl -sS https://getcomposer.org/installer | php
    - cwd: /tmp
    - unless: test -e /usr/local/bin/composer
    - require:
      - pkg: php5-fpm

move_composer:
  cmd.run:
    - name: mv composer.phar /usr/local/bin/composer
    - unless: test -e /usr/local/bin/composer
    - cwd: /tmp
    - require:
      - cmd: install_composer
