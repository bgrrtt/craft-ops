# Craft Ops

[![Join the chat at https://gitter.im/everysquare/craft-ops](https://badges.gitter.im/Join%20Chat.svg)](https://gitter.im/everysquare/craft-ops?utm_source=badge&utm_medium=badge&utm_campaign=pr-badge&utm_content=badge)

`Craft Ops` is a template which uses automation tools to build you a virtual
DevOps environment which is tailored for [Craft CMS][craft_link]. Craft itself
is already incredibly easy to setup with tools like MAMP, and this project
aims to stay that way. This project's goal is to get you past the process
of dragging files over to FTP and using commands instead. Ideally you learn 
a thing or two about [Unix-like][unix_like_link] systems in the process.

To start, the ops workflows will be built around the use of AWS and Bitbucket.
These products both offer free options and can be fully automated.  By default
this setup will stay fully within the [AWS free tier][aws_free_tier], which 
applies to all newly setup accounts.

Please also note that use of Craft is subject to their own
[license agreement][craft_license].

### Why?

The goal of this project is to keep **everything** in one place.  This cuts
out any mystery as to how the project comes together as a whole. Just by
browsing through a few files you can see how all of the services at play
are configured.  At the end of the day it makes it easier to onboard new 
people and pass the project between teams. The less reverse engineering the
better!

##### Requirements

You only need these tools installed, and both have builds for most systems.

- [Vagrant][vagrant_link]
- [VirtualBox][virtualbox_link]

##### Windows

The best way to get started with Windows is by installing the
[Git for Windows][git_windows] toolset.  This installer gives you all
the bits an pieces required to run git on Windows.  As a bonus it comes with
its own bash shell which allows you to operate your Windows system with a
Unix-like command prompt.  There are many shell options for Windows, but 
this is likely your best option.

Once you have built the `dev` VM you can also use an experimental web based
terminal @ [`http://localhost:8000/wetty`][wetty_link]. You may find this
a more enjoyable experience.

## Get started...

It is really easy, just clone this repo as the name of your project and `vagrant up`.

```shell
$ git clone https://github.com/everysquare/craft-ops.git project_name
$ cd project_name
$ vagrant up
$ vagrant ssh
$ ops setup
```

You can then hit the dev server at [`http://localhost:8000`](http://localhost:8000).

### Asset pipline

##### Harp

The Craft Ops `dev` vm runs the [Harp][harp_link] static webserver locally and uses
nginx to proxy it's output to `http://localhost:8000/static`. Any file within the
`assets` folder will be served up at this location and parsed accordingly.
This will allow you to write pure SASS or CoffeeScript without the need to fiddle
with various Grunt or Gulp configurations.  Harp is designed with a convention vs
configuration philosophy, so as long as you understand how to layout your files
it will just work.

##### Bower

You can add all of your bower components to the `bower.json` file at the root of the
project.  Just run `bower install` and anything within `bower_components` will be
available at `http://localhost:8000/static/vendor`.

#### How the configuration works

The ops setup is configured by sourcing data from a configuration object. The
object is created by merging a series of YAML files on top of each other.

`defaults.conf` - This file is the base layer and just for reference.

##### Generated after `ops setup`...

`project.conf` - This is the main file where you should put custom properties.

`private.conf` - This file is where you would store private project
data like access keys. 
>**You should add `private.conf` to `.gitignore` or encrypt it before commiting.**

##### Getting AWS credentials

After you have setup your AWS account you will need to create a new user
under [IAM][aws_iam_link].  As soon as you create this user you will be given
two keys. Download this information and save it somewhere as it will not be
available again.

You will also need to attach an **Administrator Policy** to the user. You can do this
by clicking the user and going to it's full edit view. After this you will never need
to log into AWS again.

##### Getting Bitbucket credentials

The best way to handle bitbucket is to create a "team" for your repositories to live
under.  With teams Bitbucket allows you to generate an "API key" to use instead of your
password.  You can generate this token under "Manage team" in the top right corner.
Make sure you have this key handy along with the name of the team you created.

#### Global config

If you would like to use the same credentials for all projects, you can keep all of the
above information in `~/ops.conf` on your host machine. This is a global config file
that is pulled in from your host system's `$HOME` directory when the `dev` box is
provisioned. You can keep access keys here if you need them for all projects. You
will need to run `vagrant provision` if you change this file. This will allow you
to kick off a new Craft Ops project without having to get credentials each time.

> For example you may want to keep your Bitbucket creds in the global config and
> keep individual AWS creds in private.conf for each project or client.

# Commands

Craft Ops uses the tool [Fabric][fabric_link] to manage the execution ssh commands.
This allows us to assemble super simple commands for deploying our project and
preforming common operations on it.

### Deploying

The Craft Ops setup automatically creates 3 "stages" on the web server. You have
the option of deploying to `production`, `staging`, or `preview`.

To deploy your latest commit pushed to the `bitbucket` remote you would run...

```
$ ops deploy:production
```

### Database

You can also easily prefrom operations on the database and move "dumps" around.

Let's say you wanted to dump your `production` database and use it for `dev`...

```
$ ops db:sync
```

### Asset Uploads

Perhaps you want to sync your `production` uploads to your `dev` vm...

```
$ ops uploads:sync
```

Or maybe you want to sync your `dev` uploads to `production`...

```
$ ops uploads:sync,direction=up
```

[aws_free_tier]: https://aws.amazon.com/free/
[fabric_link]: http://www.fabfile.org/
[harp_link]: http://harpjs.com/
[npm_link]: http://npmjs.org
[aws_iam_link]: https://console.aws.amazon.com/iam/
[craft_link]: https://buildwithcraft.com/
[craft_license]: https://buildwithcraft.com/license
[git_windows]: https://msysgit.github.io/
[project_conf_link]: https://github.com/everysquare/craft-ops/blob/master/project.conf#L3
[unix_like_link]:http://en.wikipedia.org/wiki/Unix-like
[vagrant_link]: http://vagrantup.com
[virtualbox_link]: http://virtualbox.org
[wetty_link]: http://localhost:8000/wetty
