# jenkins-dynamic-inventory
Dinamic inventory to run ansible plays in jenkins slaves

## Jenkins Inventory

We can't always work with those fancy cloud environments in our CI/CD with jenkins and be able to create and destroy full environments at will. Sometimes we have to deal with baremetal machines or just persistent nodes that we need to configure and reconfigure every now and then. Hence, sometimes we need to run maintenance scripts on those nodes, and that's the reason why I developed this plugin. Everybody has thought "we can just create a job and run it in every node", I wanted something different.

## Ansible Version

This inventory plugin needs **ansible >= 2.5**

## How to:

### Enable the plugin.
***


Copy the jenkins.py file in your ansible's inventory plugins directory.

Enable the jenkins plugin in your ansible's configuration file:

>[inventory]
>
> \# enable inventory plugins, default: 'host_list', 'script', 'yaml', 'ini'
>
> \#enable_plugins = host_list, virtualbox, yaml, constructed
>
> **enable_plugins = jenkins**


Instead of changing your ansible configuration and copying the plugin in your ansible's inventory plugin directory, you can run your command like that:


``` 
ANSIBLE_INVENTORY_PLUGINS=. ANSIBLE_INVENTORY_ENABLED=jenkins  ansible -i example_inventory.jenkins.yml  -m debug -a "var=hostvars[inventory_hostname]" all
``` 


### Create the jenkins inventory file.
***

This is the file that we will use when invoking the ansible command with the ```-i``` option.

``` 
ansible-playbook -i my_jenkins_inventory_file_described_here.jenkins.yml my_fancy_playbook.yml 
```

*It's name has to end with **.jenkins.yml** or **.jenkins.yaml.***


#### Parameters:

##### Jenkins Plugin
---

Parameters regarding our jenkins instance.

###### plugin (str)

	The name of this plugin: "jenkins".
    Mandatory.

###### jenkins_host (str)

	URL to the jenkis you want to control with this inventory

	Example: http://127.0.0.1:8080
    
    Mandatory.
    
###### jenkins_user (str)

	Username that will be used to query the nodes connected to our jenkins.
    You can omit this user if your computers can be seen by anonymous.

###### jenkins_pass (str)
	The password for jenkins_user.
    You can omit this value if you want the password to asked when executing the command.
    

##### Cache
---
Parameters regarding our cache configuration. We can use any of the cache plugins to store our inventory, so that we don't have to communicate with the jenkins instance every time we want to execute a playbook.


###### cache (bool)

	Enables (True) / Disables (False) the use of cache when executing this plugin.

	Default: False

Once you have enabled the use of cache, you can use whatever cache plugin you want to use. Each plugin will use their own parameters, you can find detailed documentation about cache plugins and their parameters here: [cache doc](http://docs.ansible.com/ansible/devel/plugins/cache.html)


##### Constructed
---
###### compose (dict)

	Create vars from jinja2 expressions

###### groups (dict)

	add hosts to group based on Jinja2 conditionals

###### keyed_groups (list)

	add hosts to group based on the values of a variable

###### strict(bool)

	If true make invalid entries a fatal error, otherwise skip and continue
	Since it is possible to use facts in the expressions they might not always be available 
	and we ignore those errors by default.


You can find detailed documentation about Constructed params here: [constructed doc](http://docs.ansible.com/ansible/devel/plugins/inventory/constructed.html)

#### Inventory File Example:

This is how a jenkins inventory file using jsoncache plugin would look like:

```
    plugin: jenkins

	# Jenkins plugin configuration
    # Jenkins server url configuration
    jenkins_host: http://127.0.0.1:8080/
    
    # Jenkins user that must have permissions to see the nodes connected to jenkins
    #   Omit user and password if computers can be seen by anonymous in your jenkins server.
    jenkins_user: user
    
    # The password for this user. Remember that ansible-vault is supported here.
    #   It's not a good idea to put plain text here.
    # If you omit this field, the password will be gotten via prompt
    jenkins_pass: secretpassword


    # Cache configuration. 
    # Sample for json file chache plugin configuration, just configure the chache plugin
    #   that suites better for you
    cache_connection: /path/to/the/cache/directory 
    cache_plugin: jsonfile
    cache: True


	# Constructed configuration
    # Create new hostvars using existing hostvars
    compose:
       ansible_connection: ('indows' in launcher_plugin)|ternary('winrm', 'ssh')
       # You can define your port here for windows too, if you want to.

    # Create groups depending on jinja2 filters
    groups:
        temporary_offline: (temporary_offline)

    # Create groups depending on variable values
    keyed_groups:
        - prefix: oss
          key: launcher_plugin.split('@')[0]
     

```

## Hostvars:

The plugin will include several hostvars.

###### launcher_plugin
	The plugin used by jenkins to launch scripts in this slave. I.e: "windows-slaves@1.3.1", 
	"command-launcher@1.2" or "ssh-slaves@1.26", for instance.
    
    

###### ansible_host
	When we can get this information from the launcher plugin, we will set this hostvar. 
	It will not be set if we cant find its value inspecting the launcher 
	(in command-launcher for instance we can't get its value)
    
###### ansible_port  

	If we can get the port from the launcher, we will set it. If not, we won't.
	(Basically we will only set it when using ssh-slaves launcher).
	If you need to set this variable in a windows slave, you will have to do it via 'compose'.
    
###### temporary_offline

	It will store "True" or "False" depending on if the node is set temporary offline in jenkins.
    
###### jenkins defined node properties
    
	The plugin will read the node properties defined in jenkins and will set them as hostvars in this node,
	so that you can access them from your ansible whenever you need them.

	You need to be aware that there are variables that will be ignored. Those variables are:  
    - 'launcher_plugin'
    - 'inventory_hostname'
    - 'ansible_host'
    - 'ansible_port'
    - 'temporary_offline'
    
	If you define any node property with those names, it will be ignored, and the actual
	value will NOT be overwritten.
    
    
    
## Groups:

By default this plugin will create as many groups as tags are defined in jenkins.

There are 2 mandatory groups in ansible, "all" and "ungrouped". Hence, please, we should NOT use tags with those names in jenkins if we want to use this plugin. It is a limitation that we just can't avoid, we should NEVER use those names as tags in our jenkins (if we are using this plugin), I repeat.

Apart from the tags, we can create any extra groups using the 'costructed' interface. For instance, as we can see in our jenkins-inventory-file example, we can create those groups:

	# Group by launcher (windows/linux/command....)
    keyed_groups:
        - prefix: oss
          key: launcher_plugin.split('@')[0]
    
    # Group those nodes that are temporary offline
    groups:
        temporary_offline: (temporary_offline)
        
        
## Examples:

Some basic examples about how to use the plugin:

Shows all groups in the inventory:

	ansible -i example_inventory.jenkins.yml -m debug -a "var=hostvars[inventory_hostname]['groups']" localhost


Show all hostvars in every node:

	ansible -i example_inventory.jenkins.yml -m debug -a "var=hostvars[inventory_hostname]" all
 
 Ping all nodes:
 
 	ansible -i example_inventory.jenkins.yml -m ping all
    
If we want to ping only those nodes labeled with "mylabel"

	ansible -i example_inventory.jenkins.yml -m ping mylabel
    

Add the ```-k``` parameter to the examples if you didn't share the keys.


# Limitations:

I repeat what I have said about groups names before:

>There are 2 mandatory groups in ansible, "all" and "ungrouped". Hence, please, we should NOT use tags with those names in jenkins if we want to use this plugin. It is a limitation that we just can't avoid, we should NEVER use those names as tags in our jenkins (if we are using this plugin), I repeat.
 
There is another limitation:

>When constructing variables or groups in jenkins inventory file, we only can use the variables defined by this plugin. We cannot use hostvars like 'ansible_version', for instance, to construct new ones defined in the jenkins inventory file. Hence, we should only use the variables defined in the "hostvars" section of this document (including those ones defined via node property in jenkins) to construct new ones (or new groups) via 'constructed'.


# Bugs:

Look at the following inventory. 

> localhost | SUCCESS => {
> 
>    "hostvars[inventory_hostname]['groups']": {
>    
>        "_meta": [], 
>        
>        "all": [
>        
>            "node4", 
>            
>            "node1", 
>            
>            "node3", 
>            
>            "node2"
>           
>        ], 
>        
>        "my_label_one": [
>        
>            "node1", 
>            
>            "node3"
>            
>        ], 
>        
>        "my_label_two": [
>        
>            "node2"
>            
>        ], 
>        
>        "oss_command_launcher": [
>        
>            "node3", 
>            
>            "node4"    <------------- THIS
>            
>        ], 
>        
>        "oss_ssh_slaves": [
>        
>            "node1"
>            
>        ], 
>        
>        "oss_windows_slaves": [
>        
>            "node2"
>            
>        ], 
>        
>        "temporary_offline": [
>        
>            "node1"
>            
>        ], 
>        
>        "ungrouped": [
>        
>            "node4"  <------------- THIS
>            
>        ]
>        
>    }
>    
>}


As you can see the node4 is marked as 'ungrouped' but, nevertheless, it's included in "oss_command_launcher" group. It happens because this group ("oss_command_launcher") is 'constructed' and there are ansible versions with a but that doesn't remove the nodes from 'ungrouped' group when they are included in any group via 'constructed'.

Just verify that your ansible version doesn't has this bug if this is important for you. It is reported here: [ungrouped bug](https://github.com/ansible/ansible/issues/32146)



# TODO:

Currently adding unittests
