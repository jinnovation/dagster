import importlib
from collections import namedtuple

import yaml  # sketchy

from dagster import check, seven
from dagster.core.serdes import whitelist_for_serdes

from .config import ConfigType
from .field import resolve_to_config_type


@whitelist_for_serdes
class ConfigPluginData(namedtuple('_ConfigPluginData', 'module_name plugin_name config_yaml')):
    '''Serializable tuple describing where to find a plugin and the config fragment that should
    be used to instantiate it.
    '''

    def __new__(cls, module_name, plugin_name, config_yaml):
        return super(ConfigPluginData, cls).__new__(
            cls,
            check.str_param(module_name, 'module_name'),
            check.str_param(plugin_name, 'plugin_name'),
            check.str_param(config_yaml, 'config_yaml'),
        )


def construct_from_config_plugin_data(plugin_data):
    check.inst_param(plugin_data, 'plugin_data', ConfigPluginData)

    from dagster.core.errors import DagsterInvalidConfigError
    from dagster.core.types.evaluator import evaluate_config

    try:
        module = importlib.import_module(plugin_data.module_name)
    except seven.ModuleNotFoundError:
        check.failed(
            'Couldn\'t import module {module_name} when attempting to rehydrate the '
            'plugin {plugin}'.format(
                module_name=plugin_data.module_name,
                plugin=plugin_data.module_name + '.' + plugin_data.plugin_name,
            )
        )
    try:
        plugin = getattr(module, plugin_data.plugin_name)
    except AttributeError:
        check.failed(
            (
                'Couldn\'t find plugin {plugin_name} in module {module_name} '
                'when attempting to construct it'
            ).format(module_name=plugin_data.module_name, plugin_name=plugin_data.plugin_name)
        )

    if isinstance(plugin, ConfigPlugin):
        config_dict = yaml.load(plugin_data.config_yaml)
        result = evaluate_config(plugin.config_type, config_dict)
        if not result.success:
            raise DagsterInvalidConfigError(None, result.errors, config_dict)
        return plugin.plugin_fn(result.value)

    raise check.CheckError(
        plugin,
        '{plugin_fn} in module {module_name} must be ConfigPlugin'.format(
            plugin_fn=plugin_data.plugin_name, module_name=plugin_data.module_name
        ),
    )


class ConfigPlugin(namedtuple('_ConfigPlugin', 'config_type plugin_fn')):
    def __new__(cls, config_type, plugin_fn):
        return super(ConfigPlugin, cls).__new__(
            cls,
            config_type=check.inst_param(config_type, 'config_type', ConfigType),
            plugin_fn=check.callable_param(plugin_fn, 'plugin_fn'),
        )


def config_plugin(config_class):
    '''
    Declare a config plugin.

    A config plugin
        1) declares the config that it accepts and
        2) defines a function that accepts that validated config and produces an object

    Example:

    @config_plugin(SystemNamedDict('SqliteEventLogStorageConfigPlugin', {'base_dir': Field(String)}))
    def sqlite_event_log_storage_config_plugin(plugin_config):
        return SqliteEventLogStorage(base_dir=plugin_config['base_dir'])

    This then allows one to refer to this plugin in a config file:

    run_storage:
        module: very_cool_package.event_storage
        plugin: sqlite_event_log_storage_config_plugin
        config:
            base_dir: "/path/to/thing"

    This way, users can be explicit about objects they want to load
    in a config-driven fashion, rather than rely on magical registration
    or imports that may fail.
    '''

    config_type = resolve_to_config_type(config_class)

    check.param_invariant(config_type, 'config_class', 'Must be valid config type')

    def _dec(plugin_fn):
        return ConfigPlugin(config_type, plugin_fn)

    return _dec
