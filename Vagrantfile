# -*- mode: ruby -*-
# vim: set ft=ruby ts=2 sw=2 et sts=2 :

require 'yaml'

public
def deep_merge!(other_hash)
  merge!(other_hash) do |key, oldval, newval|
    oldval.class == self.class ? oldval.deep_merge!(newval) : newval
  end
end

defaults = YAML::load_file('defaults.conf')
defaults.deep_merge!(YAML::load_file('project.conf'))

$project = defaults

if File.exist?(ENV['HOME']+'/ops.conf')
  $project.deep_merge!(YAML::load_file(ENV['HOME']+'/ops.conf'))
end
if File.exist?('private.conf')
  $project.deep_merge!(YAML::load_file('private.conf'))
end

VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|

  config.vm.box = $project['dev']['vagrant']['box']
  config.vm.box_url = $project['dev']['vagrant']['box_url']
  config.vm.box_download_checksum_type = $project['dev']['vagrant']['box_download_checksum_type']
  config.vm.box_download_checksum = $project['dev']['vagrant']['box_download_checksum']

  config.ssh.forward_agent = true

  config.vm.network "forwarded_port", guest: 8000, host: 8000

  config.vm.synced_folder ".", "/project"

  if File.exist?(ENV['HOME']+'/ops.conf')
    config.vm.provision :file,
      source: '~/ops.conf',
      destination: $project['dev']['ops_conf_path']
  end

  config.vm.provision :shell,
    path: $salt_install,
    :args => '-P -p python-dev -p python-pip -p python-git -p unzip',
    :keep_color => true

  config.vm.provision :shell,
    inline: 'sudo cp /project/salt/config/dev.conf /etc/salt/minion'

  if (/cygwin|mswin|mingw|bccwin|wince|emx/ =~ RUBY_PLATFORM) != nil
    config.vm.provision :shell,
      inline: 'sudo salt-call grains.setval vagrant_host_os windows'
  elsif (/darwin/ =~ RUBY_PLATFORM) != nil
    config.vm.provision :shell,
      inline: 'sudo salt-call grains.setval vagrant_host_os osx'
  else
    config.vm.provision :shell,
      inline: 'sudo salt-call grains.setval vagrant_host_os linux'
  end

  config.vm.provision :shell,
    inline: "sudo salt-call state.highstate --retcode-passthrough --log-level=info pillar='#{$project.to_json}'",
    :keep_color => true

end

$salt_install = "https://raw.githubusercontent.com/saltstack/salt-bootstrap/stable/bootstrap-salt.sh"
