import os
import os.path
import yaml
import sys
import pkg_resources

__all__ = ['load_plugin', 'load_simple_endpoint', 'get_config_var']

yml_config = {}

if sys.prefix == '/usr':
    conf_dir = '/etc'
    share_dir = '/usr/share'
else:
    conf_dir = os.path.join(sys.prefix, 'etc')
    share_dir = os.path.join(sys.prefix, 'share')

# Step 1: try to locate pynlp.yml
yml_config = {}
for fname in ['pynlp.yml', os.path.expanduser('~/.pynlp.yml'),
              os.path.join(conf_dir, 'pynlp.yml')]:
    if os.path.exists(fname):
        yml_config = yaml.load(open(fname))
        break


def get_config_var(path, env=None):
    """
    retrieves the config variable named ``path`` from the config file.
    Path elements that start with a $ are replaced with values from the
    dict passed as ``env``
    """
    if env is None:
        env = {}
    result = yml_config
    for e in path.split('.'):
        if e[0] == '$':
            try:
                result = result[env[e[1:]]]
            except KeyError as ex:
                try:
                    result = result['.default']
                except KeyError:
                    raise ex
        else:
            result = result[e]
    return result

def load_plugin(category, name, aux_info=None):
    """
    fetches the entry point for a plugin and calls it with the given aux_info
    """
    func = load_simple_endpoint(category, name)
    if aux_info is None:
        return func()
    else:
        return func(aux_info)


def load_simple_endpoint(category, name):
    """
    fetches the entry point for a plugin and calls it with the given aux_info
    """
    for ep in pkg_resources.iter_entry_points(category):
        if ep.name == name:
            return ep.load()
    raise KeyError(name)
