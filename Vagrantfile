# -*- mode: ruby -*-
# vim: set ft=ruby ts=2 sw=2 et sts=2 :

require 'yaml'

public
def deep_merge!(other_hash)
  merge!(other_hash) do |key, oldval, newval|
    oldval.class == self.class ? oldval.deep_merge!(newval) : newval
  end
end

$state = YAML::load_file('ops/config/defaults.conf')

if File.exist?(ENV['HOME']+'/ops.conf')
  $state.deep_merge!(YAML::load_file(ENV['HOME']+'/ops.conf'))
end
if File.exist?('ops/config/project.conf')
  $state.deep_merge!(YAML::load_file('ops/config/project.conf'))
end
if File.exist?('ops/config/private.conf')
  $state.deep_merge!(YAML::load_file('ops/config/private.conf'))
end

$state['role'] = 'dev'

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = $state['dev']['vagrant']['box']
  config.vm.box_url = $state['dev']['vagrant']['box_url']
  config.vm.box_download_checksum_type = $state['dev']['vagrant']['box_download_checksum_type']
  config.vm.box_download_checksum = $state['dev']['vagrant']['box_download_checksum']

  config.ssh.forward_agent = true

  config.vm.network "forwarded_port", guest: 8000, host: 8000
  config.vm.network "forwarded_port", guest: 3001, host: 3001 
  config.vm.network "forwarded_port", guest: 3002, host: 3002 

  config.vm.synced_folder ".", "/project"

  config.vm.synced_folder "ops/salt", "/salt"

  if $state['dev']['enable_ops_conf'] and File.exist?(ENV['HOME']+'/ops.conf')
    config.vm.provision :file,
      source: '~/ops.conf',
      destination: $state['dev']['ops_conf_path']
  end

  if $state['dev']['host_private_key']
    config.vm.provision :file,
      source: $state['dev']['host_private_key'],
      destination: '/home/vagrant/.ssh/id_rsa' 
    config.vm.provision :shell,
      inline: 'chmod 600 /home/vagrant/.ssh/id_rsa',
      :keep_color => true
    config.vm.provision :file,
      source: $state['dev']['host_public_key'],
      destination: '/home/vagrant/.ssh/id_rsa.pub' 
  end

  config.vm.provision :shell,
    inline: $install_salt,
    :keep_color => true

  config.vm.provision :shell,
    inline: $run_salt_states,
    :keep_color => true

end

$run_salt_states = <<SCRIPT
  ORANGE='\e[0;33m'
  BLUE='\e[0;34m'
  NC='\e[0m' # No Color

  if [[ `which salt-call` == "/usr/bin/salt-call" ]]
    then
      curl -L https://github.com/everysquare/formula/archive/#{$state['formula']['ref']}.tar.gz -s -o /tmp/formula.tar.gz >/dev/null

      if [ `md5sum /tmp/formula.tar.gz | awk '{ print $1 }'` != "#{$state['formula']['md5']}" ]
        then exit 1
      fi

      tar -xvf /tmp/formula.tar.gz -C /salt/roots --strip-components=1 >/dev/null

      rm /tmp/formula.tar.gz

      chown -R vagrant /salt

      chgrp -R vagrant /salt

      echo "[${BLUE}Running Salt states (May take up to 40 minutes the first time)...${NC}]" 

      sudo salt-call state.highstate --force-color --retcode-passthrough --config-dir='/salt/config' --log-level=quiet pillar='#{$state.to_json}'

      echo "[${BLUE}The machine is provisioned and ready for use :)${NC}]"
  fi
SCRIPT

$install_salt = <<SCRIPT
  ORANGE='\e[0;33m'
  BLUE='\e[0;34m'
  NC='\e[0m' # No Color

  if [[ `which salt-call` != "/usr/bin/salt-call" ]]
    then
      echo "[${BLUE}Installing Salt (May take up to 10 minutes)...${NC}]"

      cd /tmp

      wget https://github.com/saltstack/salt-bootstrap/archive/v2015.08.06.tar.gz -q >/dev/null

      if [ `md5sum v2015.08.06.tar.gz | awk '{ print $1 }'` != "60110888b0af976640259dea5f9b6727" ]
        then exit 1
      fi

      tar -xvf v2015.08.06.tar.gz >/dev/null

      sudo sh salt-bootstrap-2015.08.06/bootstrap-salt.sh -P -p python-dev -p python-pip -p python-git -p unzip >/dev/null

  else
    echo "[${ORANGE}Salt is installed.${NC}]"
  fi
SCRIPT
