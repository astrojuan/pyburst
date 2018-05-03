"""
Standardised strings/labels/paths for grid models/batches/files
"""

import os

MODELS_PATH = os.environ['KEPLER_MODELS']
GRIDS_PATH = os.environ['KEPLER_GRIDS']


def source_shorthand(source):
    """Expands source aliases (e.g. 4u ==> 4u1820)
    """
    if source == '4u':
        return '4u1820'
    elif source == 'gs':
        return 'gs1826'
    else:
        return source


# ======================================================
# Basic strings
# ======================================================
def get_batch_string(batch, source):
    return f'{source}_{batch}'


def get_run_string(run, basename='xrb'):
    return f'{basename}{run}'


# ======================================================
# Top level paths
# ======================================================
def get_source_path(source):
    return os.path.join(GRIDS_PATH, 'sources', source)


def get_analyser_path(source):
    return os.path.join(GRIDS_PATH, 'analyser', source)


# ======================================================
# Misc. paths
# ======================================================
def get_batch_models_path(batch, source):
    batch_str = get_batch_string(batch, source)
    return os.path.join(MODELS_PATH, batch_str)


def get_model_path(run, batch, source, basename='xrb'):
    batch_path = get_batch_models_path(batch, source)
    run_str = get_run_string(run, basename=basename)
    return os.path.join(batch_path, run_str)


def get_source_subdir(source, dir_):
    source_path = get_source_path(source)
    return os.path.join(source_path, dir_)


# ======================================================
# Misc. files
# ======================================================
def get_batch_filename(batch, source, prefix, extension=''):
    batch_str = get_batch_string(batch, source)
    return f'{prefix}_{batch_str}{extension}'


def get_source_filename(source, prefix, extension=''):
    return f'{prefix}_{source}{extension}'


def get_params_filename(source):
    return get_source_filename(source, prefix='params', extension='.txt')


def get_summ_filename(source):
    return get_source_filename(source, prefix='summ', extension='.txt')


def get_params_filepath(source):
    params_path = get_source_subdir(source, 'params')
    params_filename = get_params_filename(source)
    return os.path.join(params_path, params_filename)


def get_summ_filepath(source):
    params_path = get_source_subdir(source, 'summ')
    params_filename = get_summ_filename(source)
    return os.path.join(params_path, params_filename)


def get_model_table_filepath(batch, source, filename='MODELS.txt'):
    path = get_batch_models_path(batch, source)
    return os.path.join(path, filename)
