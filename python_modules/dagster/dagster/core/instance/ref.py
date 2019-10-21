import os
from collections import namedtuple

import yaml

from dagster import check
from dagster.core.serdes import whitelist_for_serdes
from dagster.core.types.config_plugin import ConfigPluginData

from .config import DAGSTER_CONFIG_YAML_FILENAME, dagster_feature_set, dagster_instance_config


def _runs_directory(base):
    return os.path.join(base, 'history', '')


def _compute_logs_directory(base):
    return os.path.join(base, 'storage')


def _event_logs_directory(base):
    return os.path.join(base, 'history', 'runs', '')


def configurable_class_data_or_default(config_value, field_name, default):
    if config_value.get(field_name):
        return ConfigPluginData(
            config_value[field_name]['module'],
            config_value[field_name]['plugin'],
            config_value[field_name]['config'],
        )
    return default


@whitelist_for_serdes
class InstanceRef(
    namedtuple(
        '_InstanceRef',
        'feature_set local_artifact_storage_data run_storage_data event_storage_data compute_logs_data',
    )
):
    def __new__(
        self,
        feature_set,
        local_artifact_storage_data,
        run_storage_data,
        event_storage_data,
        compute_logs_data=None,
    ):
        return super(self, InstanceRef).__new__(
            self,
            feature_set=check.opt_list_param(feature_set, 'feature_set'),
            local_artifact_storage_data=check.inst_param(
                local_artifact_storage_data, 'local_artifact_storage_data', ConfigPluginData
            ),
            run_storage_data=check.inst_param(
                run_storage_data, 'run_storage_data', ConfigPluginData
            ),
            event_storage_data=check.inst_param(
                event_storage_data, 'event_storage_data', ConfigPluginData
            ),
            compute_logs_data=check.inst_param(
                compute_logs_data, 'compute_logs_data', ConfigPluginData
            ),
        )

    @staticmethod
    def from_dir(base_dir, config_filename=DAGSTER_CONFIG_YAML_FILENAME):

        config_value = dagster_instance_config(base_dir, config_filename=config_filename)

        local_artifact_storage_data = configurable_class_data_or_default(
            config_value,
            'local_artifact_storage',
            ConfigPluginData(
                'dagster.core.storage.root',
                'local_artifact_storage_config_plugin',
                {'base_dir': base_dir},
            ),
        )
        run_storage_data = configurable_class_data_or_default(
            config_value,
            'run_storage',
            ConfigPluginData(
                'dagster.core.storage.sqlite_run_storage',
                'sqlite_run_storage_config_plugin',
                {'base_dir': _runs_directory(base_dir)},
            ),
        )

        event_storage_data = configurable_class_data_or_default(
            config_value,
            'event_log_storage',
            ConfigPluginData(
                'dagster.core.storage.event_log',
                'sqlite_event_log_storage_config_plugin',
                {'base_dir': _event_logs_directory(base_dir)},
            ),
        )

        compute_logs_data = configurable_class_data_or_default(
            config_value,
            'compute_logs',
            ConfigPluginData(
                'dagster.core.storage.local_compute_log_manager',
                'local_compute_log_manager_config_plugin',
                {'base_dir': _compute_logs_directory(base_dir)},
            ),
        )

        return InstanceRef(
            feature_set=dagster_feature_set(base_dir),
            local_artifact_storage_data=local_artifact_storage_data,
            run_storage_data=run_storage_data,
            event_storage_data=event_storage_data,
            compute_logs_data=compute_logs_data,
        )
